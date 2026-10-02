import unittest
from unittest.mock import Mock, patch

import numpy as np

from app.infra.camera.stream import CameraStream, build_authenticated_url, candidate_urls


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

    def test_reconnects_to_active_stream(self):
        stream = CameraStream()
        previous = Mock()
        replacement = Mock()
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        stream._capture = previous
        stream._active_url = "rtsp://camera/live"
        stream._urls = [stream._active_url]
        stream._stop.clear()

        with patch.object(stream, "_open_capture", return_value=(replacement, frame)):
            connected = stream._reconnect()

        self.assertTrue(connected)
        previous.release.assert_called_once()
        self.assertTrue(stream.status.connected)
        self.assertEqual(stream.status.message, "Ao vivo")
        self.assertIs(stream._capture, replacement)


if __name__ == "__main__":
    unittest.main()
