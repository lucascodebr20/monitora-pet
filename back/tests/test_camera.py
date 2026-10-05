import unittest
import threading
from unittest.mock import Mock, patch

import numpy as np

from app.infra.camera.stream import (
    RTSP_CAPTURE_OPTIONS,
    CameraStream,
    build_authenticated_url,
    candidate_urls,
)
from app.services.camera_service import CameraService


class CameraUrlTests(unittest.TestCase):
    def test_rtsp_transport_prefers_tcp_but_allows_udp_fallback(self):
        self.assertEqual(RTSP_CAPTURE_OPTIONS, "rtsp_flags;prefer_tcp")

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

    def test_disconnect_waits_for_active_read_before_releasing_capture(self):
        stream = CameraStream()
        read_started = threading.Event()
        finish_read = threading.Event()
        read_finished = threading.Event()
        capture = Mock()

        def read():
            read_started.set()
            finish_read.wait(timeout=2)
            read_finished.set()
            return False, None

        capture.read.side_effect = read
        capture.release.side_effect = lambda: self.assertTrue(read_finished.is_set())
        stream._capture = capture
        stream._urls = ["rtsp://camera/live"]
        stream._active_url = stream._urls[0]
        stream._stop.clear()
        stream._thread = threading.Thread(target=stream._read_loop, daemon=True)
        stream._thread.start()
        self.assertTrue(read_started.wait(timeout=1))

        disconnect_thread = threading.Thread(target=stream.disconnect)
        disconnect_thread.start()
        self.assertFalse(capture.release.called)
        finish_read.set()
        disconnect_thread.join(timeout=2)

        self.assertFalse(disconnect_thread.is_alive())
        capture.release.assert_called_once()


class CameraDiscoveryTests(unittest.TestCase):
    @patch("app.services.camera_service.discover_all")
    def test_registered_cameras_are_removed_from_discovery(self, discover_all):
        discover_all.return_value = [
            {"ip": "192.168.15.20", "name": "Câmera cadastrada"},
            {"ip": "192.168.15.21", "name": "Câmera nova"},
        ]
        repository = Mock()
        repository.list.return_value = [{"ip": "192.168.15.20"}]
        service = CameraService(repository, Mock())

        self.assertEqual(service.discover(), [{"ip": "192.168.15.21", "name": "Câmera nova"}])

    @patch("app.services.camera_service.fallback_scan")
    @patch("app.services.camera_service.discover_all")
    def test_fallback_search_filters_registered_cameras(self, discover_all, fallback_scan):
        fallback_scan.return_value = [
            {"ip": "192.168.15.20", "name": "Câmera cadastrada"},
            {"ip": "192.168.15.22", "name": "Câmera nova"},
        ]
        repository = Mock()
        repository.list.return_value = [{"ip": "192.168.15.20"}]
        service = CameraService(repository, Mock())

        self.assertEqual(service.discover(fallback=True), [{"ip": "192.168.15.22", "name": "Câmera nova"}])
        fallback_scan.assert_called_once_with()
        discover_all.assert_not_called()


if __name__ == "__main__":
    unittest.main()
