from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import quote, urlsplit, urlunsplit

# Prefere TCP, mas permite que o FFmpeg volte para UDP quando a câmera não
# oferece transporte RTSP intercalado (resposta 461 Unsupported Transport).
RTSP_CAPTURE_OPTIONS = "rtsp_flags;prefer_tcp"
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", RTSP_CAPTURE_OPTIONS)

import cv2
import numpy as np

cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)


COMMON_RTSP_PATHS = (
    "/live/ch00_0",
    "/live/ch00_1",
    "/11",
    "/12",
    "/Streaming/Channels/101",
    "/Streaming/Channels/102",
    "/cam/realmonitor?channel=1&subtype=0",
    "/cam/realmonitor?channel=1&subtype=1",
)
MAX_READ_FAILURES = 2
RECONNECT_DELAY_SECONDS = 1.5


class CameraConnectionError(RuntimeError):
    pass


def build_authenticated_url(raw_url: str, username: str, password: str) -> str:
    parts = urlsplit(raw_url)
    if parts.scheme.lower() != "rtsp" or not parts.hostname:
        raise ValueError("A URL deve começar com rtsp:// e conter um endereço válido.")
    port = f":{parts.port}" if parts.port else ""
    auth = f"{quote(username, safe='')}:{quote(password, safe='')}@" if username else ""
    return urlunsplit((parts.scheme, f"{auth}{parts.hostname}{port}", parts.path, parts.query, parts.fragment))


def candidate_urls(ip: str, username: str, password: str, manual_url: str | None) -> list[str]:
    if manual_url:
        return [build_authenticated_url(manual_url.strip(), username, password)]
    return [build_authenticated_url(f"rtsp://{ip}:554{path}", username, password) for path in COMMON_RTSP_PATHS]


def authenticate_urls(urls: list[str], username: str, password: str) -> list[str]:
    return [build_authenticated_url(url, username, password) for url in urls]


@dataclass
class CameraStatus:
    connected: bool = False
    message: str = "Desconectada"
    width: int = 0
    height: int = 0
    last_frame_at: float = 0.0


class CameraStream:
    def __init__(self) -> None:
        self._lifecycle_lock = threading.Lock()
        self._capture: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._frame: bytes | None = None
        self._raw_frame: np.ndarray | None = None
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._urls: list[str] = []
        self._active_url: str | None = None
        self._timeout_seconds = 5.0
        self.status = CameraStatus()

    def connect(self, urls: list[str], timeout_seconds: float = 5.0) -> None:
        with self._lifecycle_lock:
            if not self._disconnect_locked():
                raise CameraConnectionError("A conexão anterior da câmera ainda está sendo encerrada.")
            self._urls = list(dict.fromkeys(urls))
            self._timeout_seconds = timeout_seconds
            last_error = "Não foi possível abrir o stream."
            for url in self._urls:
                capture, frame = self._open_capture(url)
                if capture is not None and frame is not None and self._activate_capture(capture, frame):
                    self._active_url = url
                    self._stop.clear()
                    self._thread = threading.Thread(target=self._read_loop, name="camera-reader", daemon=True)
                    self._thread.start()
                    return
                last_error = "O stream abriu, mas não entregou imagens."
            self.status = CameraStatus(False, last_error)
            self._urls.clear()
            raise CameraConnectionError(last_error)

    def _open_capture(self, url: str) -> tuple[cv2.VideoCapture | None, np.ndarray | None]:
        timeout_ms = int(self._timeout_seconds * 1000)
        capture = cv2.VideoCapture(
            url,
            cv2.CAP_FFMPEG,
            [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                timeout_ms,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                timeout_ms,
            ],
        )
        if capture.isOpened():
            ok, frame = capture.read()
            if ok and frame is not None:
                return capture, frame
        capture.release()
        return None, None

    def _activate_capture(self, capture: cv2.VideoCapture, frame: np.ndarray) -> bool:
        encoded, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not encoded:
            capture.release()
            return False
        with self._condition:
            self._capture = capture
            self._frame = jpeg.tobytes()
            self._raw_frame = frame.copy()
            self.status = CameraStatus(True, "Ao vivo", frame.shape[1], frame.shape[0], time.time())
            self._condition.notify_all()
        return True

    def _read_loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            capture = self._capture
            if capture is None:
                if not self._reconnect():
                    return
                failures = 0
                continue
            ok, frame = capture.read()
            if not ok or frame is None:
                failures += 1
                if failures >= MAX_READ_FAILURES:
                    if not self._reconnect():
                        return
                    failures = 0
                else:
                    self._stop.wait(0.1)
                continue
            failures = 0
            encoded, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if encoded:
                with self._condition:
                    self._frame = jpeg.tobytes()
                    self._raw_frame = frame.copy()
                    self.status.last_frame_at = time.time()
                    self._condition.notify_all()

    def _reconnect(self) -> bool:
        capture = self._capture
        self._capture = None
        if capture is not None:
            capture.release()
        with self._condition:
            width = self.status.width
            height = self.status.height
            self._frame = None
            self._raw_frame = None
            self.status = CameraStatus(False, "Reconectando", width, height, self.status.last_frame_at)
            self._condition.notify_all()
        if not self._active_url:
            return False
        while not self._stop.is_set():
            replacement, frame = self._open_capture(self._active_url)
            if self._stop.is_set():
                if replacement is not None:
                    replacement.release()
                return False
            if replacement is not None and frame is not None and self._activate_capture(replacement, frame):
                return True
            if self._stop.wait(RECONNECT_DELAY_SECONDS):
                return False
        return False

    def frames(self) -> Iterator[bytes]:
        last_frame: bytes | None = None
        while self._urls and not self._stop.is_set():
            with self._condition:
                self._condition.wait_for(
                    lambda: (self._frame is not None and self._frame is not last_frame) or self._stop.is_set(),
                    timeout=2,
                )
                frame = self._frame
            if frame is not None and frame is not last_frame:
                last_frame = frame
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

    def latest_frame(self) -> np.ndarray | None:
        with self._condition:
            return self._raw_frame.copy() if self.status.connected and self._raw_frame is not None else None

    def snapshot(self) -> bytes | None:
        with self._condition:
            return bytes(self._frame) if self._frame is not None else None

    def disconnect(self) -> None:
        with self._lifecycle_lock:
            self._disconnect_locked()

    def _disconnect_locked(self) -> bool:
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=self._timeout_seconds + 1)
        if thread is not None and thread.is_alive():
            self.status.connected = False
            self.status.message = "Encerrando conexão anterior"
            return False
        capture = self._capture
        self._capture = None
        if capture is not None:
            capture.release()
        self._thread = None
        self._frame = None
        self._raw_frame = None
        self._urls.clear()
        self._active_url = None
        self.status = CameraStatus()
        return True
