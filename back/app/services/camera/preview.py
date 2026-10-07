from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.domain.errors import EntityNotFoundError
from app.infra.camera.manager import CameraManager
from app.infra.media.recording_reader import RecordingReader, RecordingUnreadableError
from app.infra.media.snapshot_store import SnapshotStore
from app.infra.repositories.recording_repository import RecordingRepository
from app.services.camera.service import CameraService


class CameraPreviewService:
    def __init__(
        self,
        camera_service: CameraService,
        manager: CameraManager,
        recordings: RecordingRepository,
        reader_factory: Callable[[Path], Any] = RecordingReader,
    ) -> None:
        self.camera_service = camera_service
        self.manager = manager
        self.recordings = recordings
        self.reader_factory = reader_factory

    def preview(self, camera_id: str) -> bytes:
        self.camera_service.get(camera_id)
        snapshot = self.manager.snapshot(camera_id)
        if snapshot:
            return snapshot
        for recording in reversed(self.recordings.list(camera_id)):
            if recording["status"] == "FAILED" or not Path(recording["path"]).is_file():
                continue
            try:
                frame = self.reader_factory(Path(recording["path"])).first_frame()
            except RecordingUnreadableError:
                continue
            encoded = SnapshotStore.encode(frame) if frame is not None else None
            if encoded:
                return encoded
        raise EntityNotFoundError("Sem imagem disponível. Conecte a câmera ou importe uma gravação.")
