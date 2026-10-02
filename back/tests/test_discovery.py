import unittest
from unittest.mock import patch

from app.infra.camera.discovery import fallback_scan


class DiscoveryClassificationTests(unittest.TestCase):
    @patch("app.infra.camera.discovery.device_information", return_value={})
    @patch("app.infra.camera.discovery.local_ipv4_addresses", return_value=["192.168.15.18"])
    @patch("app.infra.camera.discovery.scan_subnet")
    def test_rtsp_camera_is_named_and_ranked_first(self, scan_subnet, _interfaces, _identity):
        scan_subnet.return_value = {
            "192.168.15.1": [80],
            "192.168.15.12": [80, 8081],
            "192.168.15.21": [80, 443, 554, 8899],
        }

        devices = fallback_scan()

        self.assertEqual(devices[0]["ip"], "192.168.15.21")
        self.assertEqual(devices[0]["name"], "Câmera provável")
        self.assertEqual(devices[0]["confidence"], "high")
        self.assertEqual(devices[-1]["name"], "Outro dispositivo da rede")


if __name__ == "__main__":
    unittest.main()
