import unittest
from unittest.mock import patch

from app.infra.camera.onvif import device_information


class OnvifTests(unittest.TestCase):
    @patch("app.infra.camera.onvif._call")
    def test_reads_device_identity(self, call):
        import xml.etree.ElementTree as ET

        call.return_value = ET.fromstring(
            "<Envelope><Manufacturer>NVT</Manufacturer><Model>JA-A12</Model></Envelope>"
        )
        self.assertEqual(device_information("192.168.1.2"), {"manufacturer": "NVT", "model": "JA-A12"})


if __name__ == "__main__":
    unittest.main()
