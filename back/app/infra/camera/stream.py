from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import quote, urlsplit, urlunsplit

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

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
        self._capture: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._frame: bytes | None = None
        self._raw_frame: np.ndarray | None = None
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self.status = CameraStatus()

    def connect(self, urls: list[str], timeout_seconds: float = 5.0) -> None:
        self.disconnect()
        last_error = "Não foi possível abrir o stream."
        for url in urls:
            timeout_ms = int(timeout_seconds * 1000)
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
                    encoded, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                    if encoded:
                        self._capture = capture
                        self._frame = jpeg.tobytes()
                        self._raw_frame = frame.copy()
                        self.status = CameraStatus(True, "Ao vivo", frame.shape[1], frame.shape[0], time.time())
                        self._stop.clear()
                        self._thread = threading.Thread(target=self._read_loop, name="camera-reader", daemon=True)
                        self._thread.start()
                        return
                last_error = "O stream abriu, mas não entregou imagens."
            capture.release()
        self.status = CameraStatus(False, last_error)
        raise CameraConnectionError(last_error)

    def _read_loop(self) -> None:
        failures = 0
        while not self._stop.is_set() and self._capture is not None:
            ok, frame = self._capture.read()
            if not ok or frame is None:
                failures += 1
                if failures >= 20:
                    self.status.connected = False
                    self.status.message = "Sinal interrompido"
                    break
                time.sleep(0.1)
                continue
            failures = 0
            encoded, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if encoded:
                with self._condition:
                    self._frame = jpeg.tobytes()
                    self._raw_frame = frame.copy()
                    self.status.last_frame_at = time.time()
                    self._condition.notify_all()

    def frames(self) -> Iterator[bytes]:
        last_frame: bytes | None = None
        while self.status.connected and not self._stop.is_set():
            with self._condition:
                self._condition.wait_for(lambda: self._frame is not last_frame or self._stop.is_set(), timeout=2)
                frame = self._frame
            if frame is not None and frame is not last_frame:
                last_frame = frame
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

    def latest_frame(self) -> np.ndarray | None:
        with self._condition:
            return self._raw_frame.copy() if self._raw_frame is not None else None

    def snapshot(self) -> bytes | None:
        with self._condition:
            return bytes(self._frame) if self._frame is not None else None

    def disconnect(self) -> None:
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._frame = None
        self._raw_frame = None
        self.status = CameraStatus()
