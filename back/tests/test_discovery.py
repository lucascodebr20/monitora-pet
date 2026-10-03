import unittest
from unittest.mock import MagicMock, patch

from app.infra.camera.discovery import device_hostname, device_web_title, fallback_scan


class DiscoveryClassificationTests(unittest.TestCase):
    @patch("app.infra.camera.discovery.socket.gethostbyaddr", return_value=("motorola-50401b", [], ["192.168.15.1"]))
    def test_device_hostname_uses_reverse_dns_name(self, _gethostbyaddr):
        self.assertEqual(device_hostname("192.168.15.1"), "motorola-50401b")

    @patch("app.infra.camera.discovery.urlopen")
    def test_device_web_title_identifies_management_page(self, urlopen):
        response = MagicMock()
        urlopen.return_value.__enter__.return_value = response

        for provider in ("Vivo", "Claro"):
            with self.subTest(provider=provider):
                response.read.return_value = f"<html><title>{provider}</title></html>".encode()
                self.assertEqual(device_web_title("192.168.15.1", {80}), provider)

    @patch("app.infra.camera.discovery.discover_ssdp", return_value={})
    @patch("app.infra.camera.discovery.default_gateway_ipv4", return_value="192.168.15.1")
    @patch("app.infra.camera.discovery.device_web_title", side_effect=lambda ip, ports: "Vivo" if ip == "192.168.15.1" else "")
    @patch("app.infra.camera.discovery.device_hostname", side_effect=lambda ip: "motorola-50401b" if ip == "192.168.15.1" else "")
    @patch("app.infra.camera.discovery.device_information", return_value={})
    @patch("app.infra.camera.discovery.local_ipv4_addresses", return_value=["192.168.15.18"])
    @patch("app.infra.camera.discovery.scan_subnet")
    def test_rtsp_camera_is_named_and_ranked_first(self, scan_subnet, _interfaces, _identity, _hostname, _web_title, _gateway, _ssdp):
        scan_subnet.return_value = {
            "192.168.15.1": [80],
            "192.168.15.12": [80, 8081],
            "192.168.15.21": [80, 443, 554, 8899],
        }

        devices = fallback_scan()

        self.assertEqual(devices[0]["ip"], "192.168.15.21")
        self.assertEqual(devices[0]["name"], "Câmera provável")
        self.assertEqual(devices[0]["confidence"], "high")
        self.assertEqual(devices[-1]["name"], "motorola-50401b")
        self.assertEqual(devices[-1]["hostname"], "motorola-50401b")
        self.assertEqual(devices[-1]["web_title"], "Vivo")
        self.assertEqual(devices[-1]["reason"], "Gateway padrão da rede · Não é uma câmera")
        self.assertEqual(devices[-1]["device_type"], "router")

    @patch("app.infra.camera.discovery.discover_ssdp", return_value={})
    @patch("app.infra.camera.discovery.default_gateway_ipv4", return_value="192.168.15.1")
    @patch("app.infra.camera.discovery.device_web_title", return_value="")
    @patch("app.infra.camera.discovery.device_hostname", return_value="petcam.local")
    @patch("app.infra.camera.discovery.device_information", return_value={"manufacturer": "Acme", "model": "Pet Cam"})
    @patch("app.infra.camera.discovery.local_ipv4_addresses", return_value=["192.168.15.18"])
    @patch("app.infra.camera.discovery.scan_subnet", return_value={"192.168.15.21": [554, 8899]})
    def test_device_identity_is_returned(self, _scan_subnet, _interfaces, _identity, _hostname, _web_title, _gateway, _ssdp):
        device = fallback_scan()[0]

        self.assertEqual(device["name"], "Pet Cam")
        self.assertEqual(device["manufacturer"], "Acme")
        self.assertEqual(device["model"], "Pet Cam")
        self.assertEqual(device["hostname"], "petcam.local")

    @patch("app.infra.camera.discovery.default_gateway_ipv4", return_value="192.168.15.1")
    @patch("app.infra.camera.discovery.device_web_title", return_value="")
    @patch("app.infra.camera.discovery.device_hostname", return_value="")
    @patch("app.infra.camera.discovery.device_information", return_value={})
    @patch("app.infra.camera.discovery.local_ipv4_addresses", return_value=["192.168.15.18"])
    @patch("app.infra.camera.discovery.scan_subnet", return_value={"192.168.15.8": [80]})
    @patch("app.infra.camera.discovery.discover_ssdp", return_value={"192.168.15.8": {
        "friendly_name": "TV da sala", "manufacturer": "LG", "model": "UN7310PSC", "upnp_type": "MediaRenderer"
    }})
    def test_upnp_identity_names_non_camera_device(self, _ssdp, _scan, _interfaces, _onvif, _hostname, _web, _gateway):
        device = fallback_scan()[0]

        self.assertEqual(device["name"], "UN7310PSC")
        self.assertEqual(device["friendly_name"], "TV da sala")
        self.assertEqual(device["manufacturer"], "LG")
        self.assertEqual(device["device_type"], "media_device")
        self.assertEqual(device["reason"], "Dispositivo multimídia anunciado na rede · Não é uma câmera")


if __name__ == "__main__":
    unittest.main()
