from __future__ import annotations

import ipaddress
import socket
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from app.core.config import APP_VERSION


SSDP_ADDRESS = ("239.255.255.250", 1900)
SSDP_MESSAGE = b"\r\n".join(
    (
        b"M-SEARCH * HTTP/1.1",
        b"HOST: 239.255.255.250:1900",
        b'MAN: "ssdp:discover"',
        b"MX: 1",
        b"ST: ssdp:all",
        b"",
        b"",
    )
)


def _headers(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in payload.decode("iso-8859-1", errors="ignore").splitlines()[1:]:
        key, separator, value = raw_line.partition(":")
        if separator:
            result[key.strip().lower()] = value.strip()
    return result


def _text(device: ET.Element, name: str) -> str:
    element = device.find(f"{{*}}{name}")
    return element.text.strip() if element is not None and element.text else ""


def describe(source_ip: str, location: str) -> dict[str, str]:
    parsed = urlparse(location)
    try:
        location_ip = str(ipaddress.ip_address(parsed.hostname or ""))
    except ValueError:
        return {}
    if parsed.scheme not in {"http", "https"} or location_ip != source_ip:
        return {}
    try:
        request = Request(location, headers={"User-Agent": f"VigiaPet/{APP_VERSION} device discovery"})
        with urlopen(request, timeout=1.5) as response:
            root = ET.fromstring(response.read(262_144))
    except (OSError, ValueError, ET.ParseError):
        return {}
    device = root.find(".//{*}device")
    if device is None:
        return {}
    return {
        "friendly_name": _text(device, "friendlyName"),
        "manufacturer": _text(device, "manufacturer"),
        "model": _text(device, "modelName") or _text(device, "modelNumber"),
        "upnp_type": _text(device, "deviceType"),
    }


def discover(interface_ip: str, timeout: float = 1.5) -> dict[str, dict[str, str]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(interface_ip))
    sock.settimeout(0.25)
    try:
        sock.sendto(SSDP_MESSAGE, SSDP_ADDRESS)
        responses: dict[str, str] = {}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                payload, address = sock.recvfrom(65_535)
            except socket.timeout:
                continue
            location = _headers(payload).get("location", "")
            if location:
                responses.setdefault(address[0], location)
    finally:
        sock.close()

    devices: dict[str, dict[str, str]] = {}
    for ip, location in responses.items():
        identity = describe(ip, location)
        if identity:
            devices[ip] = identity
    return devices
