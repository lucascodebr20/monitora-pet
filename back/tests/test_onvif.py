import unittest
from unittest.mock import patch

from app.infra.camera.onvif import _call, _same_device_url, device_information, stream_urls


class OnvifTests(unittest.TestCase):
    @patch("app.infra.camera.onvif._call")
    def test_reads_device_identity(self, call):
        import xml.etree.ElementTree as ET

        call.return_value = ET.fromstring(
            "<Envelope><Manufacturer>NVT</Manufacturer><Model>JA-A12</Model></Envelope>"
        )
        self.assertEqual(device_information("192.168.1.2"), {"manufacturer": "NVT", "model": "JA-A12"})

    @patch("app.infra.camera.onvif._call")
    def test_ignores_announced_media_address_on_another_host(self, call):
        import xml.etree.ElementTree as ET

        call.side_effect = [
            ET.fromstring("<Envelope><XAddr>file:///C:/Windows/win.ini</XAddr></Envelope>"),
            ET.fromstring("<Envelope><Profiles token='p1'/></Envelope>"),
            ET.fromstring("<Envelope><Uri>rtsp://192.168.1.2/live</Uri></Envelope>"),
        ]
        self.assertEqual(stream_urls("192.168.1.2", 8899), ["rtsp://192.168.1.2/live"])
        self.assertEqual(call.call_args_list[1].args[0], "http://192.168.1.2:8899/onvif/Media")
        self.assertEqual(call.call_args_list[2].args[0], "http://192.168.1.2:8899/onvif/Media")

    @patch("app.infra.camera.onvif._call")
    def test_accepts_announced_media_address_on_same_host(self, call):
        import xml.etree.ElementTree as ET

        call.side_effect = [
            ET.fromstring("<Envelope><XAddr>http://192.168.1.2:80/onvif/media_service</XAddr></Envelope>"),
            ET.fromstring("<Envelope/>"),
        ]
        self.assertEqual(stream_urls("192.168.1.2", 8899), [])
        self.assertEqual(call.call_args_list[1].args[0], "http://192.168.1.2:80/onvif/media_service")

    def test_same_device_url_rejects_other_hosts_and_schemes(self):
        default = "http://192.168.1.2:8899/onvif/Media"
        for candidate in (None, "", "file:///etc/passwd", "ftp://192.168.1.2/x", "http://10.0.0.9/onvif", "http://evil.example/"):
            self.assertEqual(_same_device_url(candidate, "192.168.1.2", default), candidate and default or default)
        self.assertEqual(_same_device_url("https://192.168.1.2/m", "192.168.1.2", default), "https://192.168.1.2/m")

    def test_call_refuses_non_http_schemes_without_opening_them(self):
        from urllib.error import URLError

        with patch("app.infra.camera.onvif.build_opener") as opener:
            with self.assertRaises(URLError):
                _call("file:///C:/Windows/win.ini", "<x/>")
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
