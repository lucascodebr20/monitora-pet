import unittest

from app.controllers.schemas.camera_schema import CameraCreateRequest, CameraCredentialsRequest
from app.domain.urls import split_url_credentials


class SplitUrlCredentialsTests(unittest.TestCase):
    def test_extracts_and_unquotes_embedded_credentials(self):
        clean, username, password = split_url_credentials("rtsp://admin:p%40ss%3Aword@192.168.1.50:554/stream?x=1")
        self.assertEqual(clean, "rtsp://192.168.1.50:554/stream?x=1")
        self.assertEqual(username, "admin")
        self.assertEqual(password, "p@ss:word")

    def test_leaves_plain_url_untouched(self):
        self.assertEqual(split_url_credentials(" rtsp://192.168.1.50/live "), ("rtsp://192.168.1.50/live", "", ""))

    def test_strips_credentials_even_with_invalid_port_or_missing_host(self):
        self.assertEqual(split_url_credentials("rtsp://admin:segredo@192.168.1.5:99999/live"), ("rtsp://192.168.1.5:99999/live", "admin", "segredo"))
        self.assertEqual(split_url_credentials("rtsp://admin:segredo@/live"), ("rtsp:///live", "admin", "segredo"))

    def test_keeps_ipv6_brackets(self):
        clean, _, _ = split_url_credentials("rtsp://u:p@[fe80::1]:554/live")
        self.assertEqual(clean, "rtsp://[fe80::1]:554/live")


class CameraSchemaTests(unittest.TestCase):
    def test_create_request_never_keeps_password_inside_url(self):
        request = CameraCreateRequest(name="Sala", ip="192.168.1.50", rtsp_url="rtsp://admin:segredo@192.168.1.50/stream")
        self.assertEqual(request.rtsp_url, "rtsp://192.168.1.50/stream")
        self.assertEqual(request.username, "admin")
        self.assertEqual(request.password, "segredo")
        self.assertNotIn("segredo", request.to_command().rtsp_url)

    def test_explicit_fields_win_over_url_credentials(self):
        request = CameraCredentialsRequest(username="outro", password="x", rtsp_url="rtsp://admin:segredo@10.0.0.2/a")
        self.assertEqual((request.username, request.password, request.rtsp_url), ("outro", "x", "rtsp://10.0.0.2/a"))

    def test_blank_url_becomes_none(self):
        self.assertIsNone(CameraCredentialsRequest(rtsp_url="   ").rtsp_url)


if __name__ == "__main__":
    unittest.main()
