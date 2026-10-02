from __future__ import annotations

from threading import Lock
from typing import Iterator

import numpy as np

from app.infra.camera.stream import CameraStream


class CameraManager:
    def __init__(self) -> None:
        self._streams: dict[str, CameraStream] = {}
        self._lock = Lock()

    def connect(self, camera_id: str, urls: list[str]) -> CameraStream:
        with self._lock:
            stream = self._streams.setdefault(camera_id, CameraStream())
        stream.connect(urls)
        return stream

    def disconnect(self, camera_id: str) -> None:
        with self._lock:
            stream = self._streams.pop(camera_id, None)
        if stream:
            stream.disconnect()

    def status(self, camera_id: str) -> dict[str, object]:
        stream = self._streams.get(camera_id)
        if not stream:
            return {"connected": False, "message": "Desconectada", "resolution": {"width": 0, "height": 0}}
        return {
            "connected": stream.status.connected,
            "message": stream.status.message,
            "resolution": {"width": stream.status.width, "height": stream.status.height},
        }

    def frames(self, camera_id: str) -> Iterator[bytes]:
        stream = self._streams.get(camera_id)
        if not stream or not stream.status.connected:
            raise KeyError(camera_id)
        return stream.frames()

    def latest_frame(self, camera_id: str) -> np.ndarray | None:
        stream = self._streams.get(camera_id)
        if not stream or not stream.status.connected:
            return None
        return stream.latest_frame()

    def snapshot(self, camera_id: str) -> bytes | None:
        stream = self._streams.get(camera_id)
        if not stream or not stream.status.connected:
            return None
        return stream.snapshot()

    def connected_ids(self) -> list[str]:
        with self._lock:
            return [camera_id for camera_id, stream in self._streams.items() if stream.status.connected]

    def disconnect_all(self) -> None:
        with self._lock:
            camera_ids = list(self._streams)
        for camera_id in camera_ids:
            self.disconnect(camera_id)
