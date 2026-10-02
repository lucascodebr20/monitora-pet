from __future__ import annotations

import ipaddress
import socket
from urllib.parse import unquote, urlparse

from app.infra.camera.onvif import device_information
from app.infra.camera.ws_discovery import discover, scan_subnet


CAMERA_PORT_WEIGHTS = {
    554: 6,
    8554: 5,
    8899: 3,
    2020: 2,
    34567: 2,
    8000: 1,
    8081: 1,
}


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
    for interface in local_ipv4_addresses():
        network = ipaddress.ip_network(f"{interface}/24", strict=False)
        try:
            for ip, ports in scan_subnet(str(network)).items():
                found.setdefault(ip, set()).update(ports)
        except OSError:
            continue
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
            name = "Outro dispositivo da rede"
            confidence = "low"
            reason = "Nenhum stream de vídeo detectado"
        identity = device_information(ip) if 8899 in ports else {}
        manufacturer = identity.get("manufacturer", "")
        model = identity.get("model", "")
        if has_rtsp and model:
            name = model
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
            }
        )

    return sorted(
        devices,
        key=lambda item: (-int(item["score"]), ipaddress.ip_address(str(item["ip"]))),
    )
