from __future__ import annotations

import base64
import hashlib
import ipaddress
import os
import xml.etree.ElementTree as ET
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
    except (OSError, ET.ParseError):
        return {}


def _same_device_url(candidate: str | None, ip: str, default: str) -> str:
    """Aceita o endereço anunciado pela câmera apenas se ele for http(s) e apontar para o
    próprio IP cadastrado. Um dispositivo malicioso não consegue redirecionar o servidor
    para outro host, esquema ou arquivo local."""
    if not candidate:
        return default
    parts = urlsplit(candidate.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
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
            uri = _text(response, "Uri")
            if uri and uri not in urls:
                urls.append(uri)
        return urls
    except (OSError, ET.ParseError):
        return []
