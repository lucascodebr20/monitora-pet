import unittest
from unittest.mock import MagicMock, patch

from app.infra.camera.ssdp import describe


class SsdpIdentityTests(unittest.TestCase):
    @patch("app.infra.camera.ssdp.urlopen")
    def test_reads_device_identity_from_upnp_description(self, urlopen):
        response = MagicMock()
        response.read.return_value = b"""<?xml version="1.0"?>
        <root xmlns="urn:schemas-upnp-org:device-1-0"><device>
          <deviceType>urn:schemas-upnp-org:device:InternetGatewayDevice:1</deviceType>
          <friendlyName>Gateway residencial</friendlyName>
          <manufacturer>Fabricante regional</manufacturer>
          <modelName>Modelo ABC</modelName>
        </device></root>"""
        urlopen.return_value.__enter__.return_value = response

        identity = describe("192.168.15.1", "http://192.168.15.1/device.xml")

        self.assertEqual(identity["friendly_name"], "Gateway residencial")
        self.assertEqual(identity["manufacturer"], "Fabricante regional")
        self.assertEqual(identity["model"], "Modelo ABC")
        self.assertIn("InternetGatewayDevice", identity["upnp_type"])

    @patch("app.infra.camera.ssdp.urlopen")
    def test_rejects_description_from_another_host(self, urlopen):
        self.assertEqual(describe("192.168.15.1", "http://203.0.113.5/device.xml"), {})
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
