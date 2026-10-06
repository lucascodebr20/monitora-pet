from __future__ import annotations

import html
import ipaddress
import re
import socket
import ssl
import struct
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from app.infra.camera.onvif import device_information
from app.infra.camera.ssdp import discover as discover_ssdp
from app.infra.camera.ws_discovery import discover, scan_subnet
from app.core.config import APP_VERSION


CAMERA_PORT_WEIGHTS = {
    554: 6,
    8554: 5,
    8899: 3,
    2020: 2,
    34567: 2,
    8000: 1,
    8081: 1,
}


def device_hostname(ip: str) -> str:
    try:
        hostname = socket.gethostbyaddr(ip)[0].strip().rstrip(".")
    except (OSError, UnicodeError):
        return ""
    return "" if hostname == ip else hostname


def default_gateway_ipv4() -> str:
    try:
        routes = Path("/proc/net/route").read_text(encoding="ascii").splitlines()[1:]
    except (OSError, UnicodeError):
        return ""
    for route in routes:
        fields = route.split()
        if len(fields) < 4 or fields[1] != "00000000" or not int(fields[3], 16) & 2:
            continue
        try:
            return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
        except (OSError, ValueError, struct.error):
            continue
    return ""


def device_web_title(ip: str, ports: set[int]) -> str:
    web_ports = [port for port in (80, 443, 8000, 8080, 8081) if port in ports]
    for port in web_ports:
        scheme = "https" if port == 443 else "http"
        default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
        address = f"{scheme}://{ip}{'' if default_port else f':{port}'}/"
        request = Request(address, headers={"User-Agent": f"MonitoraPet/{APP_VERSION} device discovery"})
        try:
            context = ssl._create_unverified_context() if scheme == "https" else None
            with urlopen(request, timeout=1.5, context=context) as response:
                body = response.read(65_536).decode("utf-8", errors="ignore")
        except (OSError, ValueError):
            continue
        match = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.IGNORECASE | re.DOTALL)
        if match:
            title = re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()
            if title:
                return title[:80]
    return ""


def local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127.") and not address.startswith("169.254."):
                addresses.add(address)
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 9))
            address = sock.getsockname()[0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


def _friendly_name(scopes: list[str], fallback: str) -> str:
    for scope in scopes:
        parsed = urlparse(scope)
        if "/name/" in parsed.path:
            return unquote(parsed.path.split("/name/", 1)[1]).replace("_", " ")
    for scope in scopes:
        parsed = urlparse(scope)
        if "/hardware/" in parsed.path:
            return unquote(parsed.path.split("/hardware/", 1)[1]).replace("_", " ")
    return f"Câmera {fallback}"


def discover_all(timeout: float = 3.0, attempts: int = 2) -> list[dict[str, object]]:
    found: dict[str, dict[str, object]] = {}
    for interface in local_ipv4_addresses():
        try:
            for device in discover(interface, timeout, attempts):
                ip = str(device["ip"])
                scopes = [str(item) for item in device.get("scopes", [])]
                found[ip] = {
                    "ip": ip,
                    "name": _friendly_name(scopes, ip),
                    "onvif": bool(device.get("xaddrs")),
                }
        except OSError:
            continue
    return sorted(found.values(), key=lambda item: ipaddress.ip_address(str(item["ip"])))


def fallback_scan() -> list[dict[str, object]]:
    found: dict[str, set[int]] = {}
    announced: dict[str, dict[str, str]] = {}
    interfaces = local_ipv4_addresses()
    for interface in interfaces:
        network = ipaddress.ip_network(f"{interface}/24", strict=False)
        try:
            for ip, ports in scan_subnet(str(network)).items():
                found.setdefault(ip, set()).update(ports)
        except OSError:
            continue
        try:
            announced.update(discover_ssdp(interface))
        except OSError:
            pass
    for ip in announced:
        found.setdefault(ip, set())
    gateway_ip = default_gateway_ipv4()
    devices: list[dict[str, object]] = []
    for ip, ports in found.items():
        score = sum(CAMERA_PORT_WEIGHTS.get(port, 0) for port in ports)
        has_rtsp = 554 in ports or 8554 in ports
        if has_rtsp:
            name = "Câmera provável"
            confidence = "high"
            reason = "Transmissão de vídeo RTSP detectada"
        elif score >= 2:
            name = "Possível câmera"
            confidence = "medium"
            reason = "Porta comum de câmera detectada"
        else:
            name = f"Dispositivo em {ip}"
            confidence = "low"
            reason = "Nenhum stream de vídeo detectado"
        identity = device_information(ip) if 8899 in ports else {}
        network_identity = announced.get(ip, {})
        manufacturer = identity.get("manufacturer", "") or network_identity.get("manufacturer", "")
        model = identity.get("model", "") or network_identity.get("model", "")
        friendly_name = network_identity.get("friendly_name", "")
        hostname = device_hostname(ip)
        upnp_type = network_identity.get("upnp_type", "")
        normalized_upnp_type = upnp_type.lower()
        is_local_host = ip in interfaces
        is_default_gateway = ip == gateway_ip
        is_router = is_default_gateway or "internetgatewaydevice" in normalized_upnp_type
        is_media_device = "mediarenderer" in normalized_upnp_type or "mediaserver" in normalized_upnp_type
        web_title = device_web_title(ip, ports) if not is_local_host and not model and not friendly_name and (is_router or not hostname) else ""
        if is_local_host:
            name = str(hostname or socket.gethostname() or "Servidor do Monitora Pet")
            reason = "Servidor do Monitora Pet · Não é uma câmera"
        elif is_router:
            name = str(model or friendly_name or hostname or "Roteador/modem da rede")
            reason = "Gateway padrão da rede · Não é uma câmera" if is_default_gateway else "Roteador anunciado na rede · Não é uma câmera"
        else:
            name = str(model or friendly_name or hostname or web_title or name)
            if confidence == "low" and is_media_device:
                reason = "Dispositivo multimídia anunciado na rede · Não é uma câmera"
            elif confidence == "low" and network_identity:
                reason = "Dispositivo identificado via UPnP · Não é uma câmera"
            elif confidence == "low" and web_title:
                reason = "Interface web detectada · Nenhum stream de vídeo detectado"
            elif confidence == "low" and not (model or friendly_name or hostname):
                name = f"Dispositivo em {ip}"
        devices.append(
            {
                "ip": ip,
                "name": name,
                "onvif": False,
                "ports": sorted(ports),
                "confidence": confidence,
                "reason": reason,
                "score": score,
                "manufacturer": manufacturer,
                "model": model,
                "friendly_name": friendly_name,
                "hostname": hostname,
                "web_title": web_title,
                "upnp_type": upnp_type,
                "device_type": "host" if is_local_host else "router" if is_router else "camera" if has_rtsp else "media_device" if is_media_device else "network_device",
            }
        )

    return sorted(
        devices,
        key=lambda item: (-int(item["score"]), ipaddress.ip_address(str(item["ip"]))),
    )
