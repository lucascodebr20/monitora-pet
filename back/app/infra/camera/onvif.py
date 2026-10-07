from __future__ import annotations

import base64
import hashlib
import ipaddress
import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPDigestAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    Request,
    build_opener,
)
from xml.sax.saxutils import escape


logger = logging.getLogger(__name__)

SOAP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  {header}<s:Body>{body}</s:Body>
</s:Envelope>"""


def _security_header(username: str, password: str) -> str:
    if not username:
        return ""
    nonce = os.urandom(16)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    digest = base64.b64encode(hashlib.sha1(nonce + created.encode() + password.encode()).digest()).decode()
    encoded_nonce = base64.b64encode(nonce).decode()
    return f"""<s:Header>
      <wsse:Security s:mustUnderstand="1"
       xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
       xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
        <wsse:UsernameToken>
          <wsse:Username>{escape(username)}</wsse:Username>
          <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{digest}</wsse:Password>
          <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{encoded_nonce}</wsse:Nonce>
          <wsu:Created>{created}</wsu:Created>
        </wsse:UsernameToken>
      </wsse:Security>
    </s:Header>"""


def _call(
    url: str,
    body: str,
    action: str = "",
    timeout: float = 3.0,
    username: str = "",
    password: str = "",
) -> ET.Element:
    payload = SOAP_TEMPLATE.format(
        header=_security_header(username, password),
        body=body,
    ).encode("utf-8")
    content_type = "application/soap+xml; charset=utf-8"
    if action:
        content_type += f'; action="{action}"'
    if urlsplit(url).scheme.lower() not in ("http", "https"):
        raise URLError(f"Endereço ONVIF não suportado: {url!r}")
    request = Request(url, data=payload, headers={"Content-Type": content_type}, method="POST")
    password_manager = HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, url, username, password)
    opener = build_opener(
        HTTPDigestAuthHandler(password_manager),
        HTTPBasicAuthHandler(password_manager),
    )
    with opener.open(request, timeout=timeout) as response:
        return ET.fromstring(response.read())


def _text(root: ET.Element, local_name: str) -> str | None:
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == local_name and element.text:
            return element.text.strip()
    return None


def device_information(
    ip: str, port: int = 8899, username: str = "", password: str = ""
) -> dict[str, str]:
    try:
        root = _call(
            f"http://{ip}:{port}/onvif/device_service",
            '<tds:GetDeviceInformation xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>',
            username=username,
            password=password,
        )
        return {
            "manufacturer": _text(root, "Manufacturer") or "",
            "model": _text(root, "Model") or "",
        }
    except (OSError, ET.ParseError) as error:
        logger.info("ONVIF sem informações do dispositivo em %s:%s: %s", ip, port, error)
        return {}


def _same_device_url(
    candidate: str | None, ip: str, default: str, schemes: tuple[str, ...] = ("http", "https")
) -> str:
    if not candidate:
        return default
    parts = urlsplit(candidate.strip())
    if parts.scheme.lower() not in schemes or not parts.hostname:
        return default
    try:
        if ipaddress.ip_address(parts.hostname) != ipaddress.ip_address(ip):
            return default
    except ValueError:
        return default
    return candidate.strip()


def stream_urls(
    ip: str, port: int = 8899, username: str = "", password: str = ""
) -> list[str]:
    try:
        capabilities = _call(
            f"http://{ip}:{port}/onvif/device_service",
            '<tds:GetCapabilities xmlns:tds="http://www.onvif.org/ver10/device/wsdl">'
            "<tds:Category>Media</tds:Category></tds:GetCapabilities>",
            username=username,
            password=password,
        )
        media_url = _same_device_url(_text(capabilities, "XAddr"), ip, f"http://{ip}:{port}/onvif/Media")
        profiles = _call(
            media_url,
            '<trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>',
            username=username,
            password=password,
        )
        tokens = [
            element.attrib["token"]
            for element in profiles.iter()
            if element.tag.rsplit("}", 1)[-1] == "Profiles" and element.attrib.get("token")
        ]
        urls: list[str] = []
        for token in tokens:
            response = _call(
                media_url,
                '<trt:GetStreamUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl">'
                '<trt:StreamSetup><tt:Stream xmlns:tt="http://www.onvif.org/ver10/schema">RTP-Unicast</tt:Stream>'
                '<tt:Transport xmlns:tt="http://www.onvif.org/ver10/schema"><tt:Protocol>RTSP</tt:Protocol>'
                f"</tt:Transport></trt:StreamSetup><trt:ProfileToken>{token}</trt:ProfileToken>"
                "</trt:GetStreamUri>",
                username=username,
                password=password,
            )
            uri = _same_device_url(_text(response, "Uri"), ip, "", ("rtsp", "rtsps"))
            if uri and uri not in urls:
                urls.append(uri)
        return urls
    except (OSError, ET.ParseError) as error:
        logger.info("ONVIF sem URLs de stream em %s:%s: %s", ip, port, error)
        return []


SEARCH_NAMESPACE = "http://www.onvif.org/ver10/search/wsdl"
REPLAY_NAMESPACE = "http://www.onvif.org/ver10/replay/wsdl"


@dataclass(frozen=True)
class RecordingSpan:
    token: str
    start: datetime
    end: datetime


class RecordingSearchError(RuntimeError):
    pass


def _children(root: ET.Element, local_name: str) -> list[ET.Element]:
    return [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == local_name]


def _child_text(element: ET.Element, local_name: str) -> str | None:
    for child in element.iter():
        if child is not element and child.tag.rsplit("}", 1)[-1] == local_name and child.text:
            return child.text.strip()
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def device_clock_offset(ip: str, port: int = 8899, username: str = "", password: str = "") -> float | None:
    try:
        before = datetime.now(timezone.utc)
        root = _call(
            f"http://{ip}:{port}/onvif/device_service",
            '<tds:GetSystemDateAndTime xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>',
            username=username,
            password=password,
        )
        after = datetime.now(timezone.utc)
    except (OSError, ET.ParseError) as error:
        logger.info("ONVIF sem data e hora em %s:%s: %s", ip, port, error)
        return None
    utc_blocks = _children(root, "UTCDateTime")
    if not utc_blocks:
        return None
    block = utc_blocks[0]
    try:
        camera_time = datetime(
            int(_child_text(block, "Year") or 0),
            int(_child_text(block, "Month") or 0),
            int(_child_text(block, "Day") or 0),
            int(_child_text(block, "Hour") or 0),
            int(_child_text(block, "Minute") or 0),
            int(_child_text(block, "Second") or 0),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None
    midpoint = before + (after - before) / 2
    return (camera_time - midpoint).total_seconds()


def recording_services(ip: str, port: int = 8899, username: str = "", password: str = "") -> dict[str, str]:
    try:
        root = _call(
            f"http://{ip}:{port}/onvif/device_service",
            '<tds:GetServices xmlns:tds="http://www.onvif.org/ver10/device/wsdl">'
            "<tds:IncludeCapability>false</tds:IncludeCapability></tds:GetServices>",
            username=username,
            password=password,
        )
    except (OSError, ET.ParseError) as error:
        logger.info("ONVIF sem lista de serviços em %s:%s: %s", ip, port, error)
        return {}
    services: dict[str, str] = {}
    for service in _children(root, "Service"):
        namespace = _child_text(service, "Namespace") or ""
        address = _same_device_url(_child_text(service, "XAddr"), ip, "")
        if not address:
            continue
        if namespace == SEARCH_NAMESPACE:
            services["search"] = address
        elif namespace == REPLAY_NAMESPACE:
            services["replay"] = address
    return services if "search" in services and "replay" in services else {}


def find_recordings(
    search_url: str, start: datetime, end: datetime, username: str = "", password: str = ""
) -> list[RecordingSpan]:
    try:
        started = _call(
            search_url,
            f'<tse:FindRecordings xmlns:tse="{SEARCH_NAMESPACE}"><tse:Scope/>'
            "<tse:KeepAliveTime>PT30S</tse:KeepAliveTime></tse:FindRecordings>",
            username=username,
            password=password,
            timeout=10.0,
        )
        token = _text(started, "SearchToken")
        if not token:
            return []
        results = _call(
            search_url,
            f'<tse:GetRecordingSearchResults xmlns:tse="{SEARCH_NAMESPACE}">'
            f"<tse:SearchToken>{escape(token)}</tse:SearchToken><tse:MinResults>1</tse:MinResults>"
            "<tse:MaxResults>100</tse:MaxResults><tse:WaitTime>PT10S</tse:WaitTime>"
            "</tse:GetRecordingSearchResults>",
            username=username,
            password=password,
            timeout=15.0,
        )
    except (OSError, ET.ParseError) as error:
        logger.warning("Falha ao consultar gravações ONVIF em %s: %s", search_url, error)
        raise RecordingSearchError("Não foi possível consultar as gravações da câmera.") from error
    spans: list[RecordingSpan] = []
    for info in _children(results, "RecordingInformation"):
        recording_token = _child_text(info, "RecordingToken")
        earliest = _parse_datetime(_child_text(info, "EarliestRecording"))
        latest = _parse_datetime(_child_text(info, "LatestRecording"))
        if not recording_token or earliest is None or latest is None:
            continue
        span_start, span_end = max(earliest, start), min(latest, end)
        if span_start < span_end:
            spans.append(RecordingSpan(recording_token, span_start, span_end))
    return spans


def replay_uri(replay_url: str, recording_token: str, ip: str, username: str = "", password: str = "") -> str | None:
    try:
        root = _call(
            replay_url,
            f'<trp:GetReplayUri xmlns:trp="{REPLAY_NAMESPACE}">'
            '<trp:StreamSetup><tt:Stream xmlns:tt="http://www.onvif.org/ver10/schema">RTP-Unicast</tt:Stream>'
            '<tt:Transport xmlns:tt="http://www.onvif.org/ver10/schema"><tt:Protocol>RTSP</tt:Protocol></tt:Transport>'
            f"</trp:StreamSetup><trp:RecordingToken>{escape(recording_token)}</trp:RecordingToken></trp:GetReplayUri>",
            username=username,
            password=password,
        )
    except (OSError, ET.ParseError) as error:
        logger.info("ONVIF sem URI de replay em %s: %s", replay_url, error)
        return None
    return _same_device_url(_text(root, "Uri"), ip, "", ("rtsp", "rtsps")) or None
