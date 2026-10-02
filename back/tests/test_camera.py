import unittest

from app.infra.camera.stream import build_authenticated_url, candidate_urls


class CameraUrlTests(unittest.TestCase):
    def test_credentials_are_escaped(self):
        url = build_authenticated_url("rtsp://192.168.1.2:554/live", "meu user", "p@ss:word")
        self.assertEqual(url, "rtsp://meu%20user:p%40ss%3Aword@192.168.1.2:554/live")

    def test_manual_url_has_priority(self):
        urls = candidate_urls("192.168.1.2", "admin", "secret", "rtsp://192.168.1.2/custom")
        self.assertEqual(urls, ["rtsp://admin:secret@192.168.1.2/custom"])

    def test_rejects_non_rtsp_url(self):
        with self.assertRaises(ValueError):
            build_authenticated_url("http://192.168.1.2/live", "admin", "secret")


if __name__ == "__main__":
    unittest.main()
