from __future__ import annotations

from typing import Protocol

import numpy as np

from app.infra.camera.manager import CameraManager
from app.infra.media.snapshot_store import SnapshotStore


class SnapshotSource(Protocol):
    def snapshot(self, camera_id: str, frame: np.ndarray) -> bytes | None: ...


class StreamSnapshotSource:
    def __init__(self, camera_manager: CameraManager) -> None:
        self.camera_manager = camera_manager

    def snapshot(self, camera_id: str, frame: np.ndarray) -> bytes | None:
        return self.camera_manager.snapshot(camera_id)


class FrameSnapshotSource:
    def __init__(self, snapshot_store: SnapshotStore) -> None:
        self.snapshot_store = snapshot_store

    def snapshot(self, camera_id: str, frame: np.ndarray) -> bytes | None:
        return self.snapshot_store.encode(frame)
