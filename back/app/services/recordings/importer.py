from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from app.domain.errors import EntityNotFoundError, OperationFailedError
from app.infra.media.fingerprint import fingerprint_file
from app.infra.media.recording_reader import RecordingReader, RecordingUnreadableError
from app.infra.repositories.recording_repository import RecordingRepository
from app.services.camera import CameraService
from app.services.event.purge import EventPurgeService

ORIGIN_FOLDER = "FOLDER"
ORIGIN_CAMERA = "CAMERA"


class RecordingImportService:
    def __init__(
        self,
        repository: RecordingRepository,
        camera_service: CameraService,
        purge: EventPurgeService,
        reader_factory: Callable[[Path], Any] = RecordingReader,
    ) -> None:
        self.repository = repository
        self.camera_service = camera_service
        self.purge = purge
        self.reader_factory = reader_factory

    def register(self, camera_id: str, path: Path, started_at: datetime, origin: str = ORIGIN_FOLDER) -> dict[str, Any]:
        self.camera_service.get(camera_id)
        path = Path(path)
        if not path.is_file():
            raise EntityNotFoundError("O arquivo da gravação não foi encontrado.")
        fingerprint = fingerprint_file(path)
        existing = self.repository.find_by_fingerprint(camera_id, fingerprint)
        if existing:
            return existing
        try:
            info = self.reader_factory(path).probe()
        except RecordingUnreadableError as error:
            raise OperationFailedError(str(error)) from error
        return self.repository.create({
            "camera_id": camera_id,
            "origin": origin,
            "path": str(path),
            "fingerprint": fingerprint,
            "size_bytes": path.stat().st_size,
            "started_at": started_at.isoformat(),
            "ended_at": (started_at + timedelta(seconds=info.duration_seconds)).isoformat(),
        })

    def reprocess(self, recording_id: str) -> dict[str, Any]:
        recording = self.get(recording_id)
        if not Path(recording["path"]).is_file():
            raise OperationFailedError("O arquivo original não está mais disponível para reprocessamento.")
        self.purge.purge_recording(recording_id)
        self.repository.reset(recording_id)
        return self.get(recording_id)

    def get(self, recording_id: str) -> dict[str, Any]:
        recording = self.repository.get(recording_id)
        if not recording:
            raise EntityNotFoundError("Gravação não encontrada.")
        return recording

    def list(self, camera_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.repository.list(camera_id, status)

    def pending(self, camera_id: str) -> list[dict[str, Any]]:
        return self.repository.list(camera_id, "PENDING")
