from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import socket
import time
import uuid
import xml.etree.ElementTree as ET


MULTICAST_ADDRESS = ("239.255.255.250", 3702)
CAMERA_PORTS = (80, 81, 443, 554, 2020, 8000, 8080, 8081, 8554, 8899, 34567)
SOAP_NAMESPACES = {
    "addressing": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
    "discovery": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
}


def probe_message() -> bytes:
    message_id = uuid.uuid4()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
 xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
 xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
 <e:Header>
  <w:MessageID>uuid:{message_id}</w:MessageID>
  <w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
  <w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
 </e:Header>
 <e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body>
</e:Envelope>""".encode()


def parse_response(payload: bytes, source_ip: str) -> dict[str, object]:
    result: dict[str, object] = {"ip": source_ip, "xaddrs": [], "scopes": []}
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        result["invalid_xml"] = True
        return result

    address = root.find(".//addressing:Address", SOAP_NAMESPACES)
    xaddrs = root.find(".//discovery:XAddrs", SOAP_NAMESPACES)
    scopes = root.find(".//discovery:Scopes", SOAP_NAMESPACES)
    result["endpoint"] = address.text.strip() if address is not None and address.text else None
    result["xaddrs"] = xaddrs.text.split() if xaddrs is not None and xaddrs.text else []
    result["scopes"] = scopes.text.split() if scopes is not None and scopes.text else []
    return result


def discover(interface_ip: str, timeout: float, attempts: int) -> list[dict[str, object]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(interface_ip))
    sock.settimeout(0.5)

    for _ in range(attempts):
        sock.sendto(probe_message(), MULTICAST_ADDRESS)
        time.sleep(0.2)

    devices: dict[str, dict[str, object]] = {}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            payload, address = sock.recvfrom(65_535)
        except socket.timeout:
            continue
        parsed = parse_response(payload, address[0])
        key = str(parsed.get("endpoint") or address[0])
        devices[key] = parsed

    sock.close()
    return list(devices.values())


def test_port(target: tuple[str, int], timeout: float = 0.35) -> tuple[str, int] | None:
    try:
        with socket.create_connection(target, timeout=timeout):
            return target
    except OSError:
        return None


def scan_subnet(cidr: str) -> dict[str, list[int]]:
    network = ipaddress.ip_network(cidr, strict=False)
    targets = [(str(host), port) for host in network.hosts() for port in CAMERA_PORTS]
    workers = min(128, len(targets))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        open_targets = [result for result in executor.map(test_port, targets) if result]

    candidates: dict[str, list[int]] = {}
    for host, port in open_targets:
        candidates.setdefault(host, []).append(port)
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover ONVIF cameras via WS-Discovery")
    parser.add_argument("--interface", required=True, help="local IPv4 address used for multicast")
    parser.add_argument("--timeout", type=float, default=6.0, help="response window in seconds")
    parser.add_argument("--attempts", type=int, default=3, help="number of probe packets")
    parser.add_argument(
        "--scan-subnet",
        metavar="CIDR",
        help="fallback TCP scan, for example 192.168.1.0/24",
    )
    args = parser.parse_args()

    devices = discover(args.interface, args.timeout, args.attempts)
    if devices:
        for index, device in enumerate(devices, start=1):
            print(f"Camera {index}: {device['ip']}")
            for xaddr in device["xaddrs"]:
                print(f"  ONVIF: {xaddr}")
            for scope in device["scopes"]:
                print(f"  Scope: {scope}")
    else:
        print("No ONVIF cameras responded.")

    candidates = scan_subnet(args.scan_subnet) if args.scan_subnet else {}
    if args.scan_subnet:
        if candidates:
            print("Fallback candidates:")
            for host, ports in candidates.items():
                print(f"  {host}: {', '.join(map(str, ports))}")
        else:
            print("No fallback candidates found on common camera ports.")

    return 0 if devices or candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
