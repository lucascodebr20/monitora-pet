from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from app.domain.errors import EntityNotFoundError, InvalidDomainValueError, OperationFailedError
from app.infra.media.filename_time import is_video_file, start_time_from_modification, start_time_from_name
from app.infra.media.fingerprint import fingerprint_file
from app.infra.media.recording_reader import RecordingReader, RecordingUnreadableError
from app.infra.repositories.recording_repository import RecordingRepository
from app.infra.repositories.watched_folder_repository import WatchedFolderRepository
from app.services.camera import CameraService
from app.services.event.purge import EventPurgeService

ORIGIN_FOLDER = "FOLDER"
ORIGIN_CAMERA = "CAMERA"
TIME_PROTOCOL = "PROTOCOL"
TIME_FILENAME = "FILENAME"
TIME_MODIFIED = "MODIFIED"
TIME_MANUAL = "MANUAL"
MAX_FILES_PER_SCAN = 500


class RecordingImportService:
    def __init__(
        self,
        repository: RecordingRepository,
        camera_service: CameraService,
        purge: EventPurgeService,
        reader_factory: Callable[[Path], Any] = RecordingReader,
        folders: WatchedFolderRepository | None = None,
    ) -> None:
        self.repository = repository
        self.camera_service = camera_service
        self.purge = purge
        self.reader_factory = reader_factory
        self.folders = folders

    def register(
        self,
        camera_id: str,
        path: Path,
        started_at: datetime | None,
        origin: str = ORIGIN_FOLDER,
        time_source: str | None = None,
    ) -> dict[str, Any]:
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
        if started_at is None:
            started_at = start_time_from_name(path)
            time_source = TIME_FILENAME if started_at else TIME_MODIFIED
            started_at = started_at or start_time_from_modification(path, info.duration_seconds)
        return self.repository.create({
            "camera_id": camera_id,
            "origin": origin,
            "path": str(path),
            "fingerprint": fingerprint,
            "size_bytes": path.stat().st_size,
            "started_at": started_at.isoformat(),
            "ended_at": (started_at + timedelta(seconds=info.duration_seconds)).isoformat(),
            "time_source": time_source or TIME_PROTOCOL,
        })

    def import_path(self, camera_id: str, path: Path) -> list[dict[str, Any]]:
        path = Path(path)
        if path.is_dir():
            return self.scan_folder(camera_id, path)
        return [self.register(camera_id, path, None)]

    def scan_folder(self, camera_id: str, folder: Path) -> list[dict[str, Any]]:
        self.camera_service.get(camera_id)
        folder = Path(folder)
        if not folder.is_dir():
            raise EntityNotFoundError("A pasta informada não foi encontrada.")
        files = sorted((item for item in folder.rglob("*") if is_video_file(item)), key=lambda item: item.name)
        registered: list[dict[str, Any]] = []
        for file in files[:MAX_FILES_PER_SCAN]:
            try:
                registered.append(self.register(camera_id, file, None))
            except OperationFailedError:
                continue
        return registered

    def scan_watched_folders(self, camera_id: str | None = None) -> list[dict[str, Any]]:
        if not self.folders:
            return []
        registered: list[dict[str, Any]] = []
        for folder in self.folders.list(camera_id):
            if Path(folder["path"]).is_dir():
                registered.extend(self.scan_folder(folder["camera_id"], Path(folder["path"])))
                self.folders.mark_scanned(folder["id"])
        return registered

    def adjust_start(self, recording_id: str, started_at: datetime) -> dict[str, Any]:
        recording = self.get(recording_id)
        duration = datetime.fromisoformat(recording["ended_at"]) - datetime.fromisoformat(recording["started_at"])
        if recording["status"] == "PROCESSING":
            raise InvalidDomainValueError("Aguarde o processamento terminar para ajustar o horário.")
        if recording["status"] in ("DONE", "FAILED", "SKIPPED"):
            self.purge.purge_recording(recording_id)
            self.repository.reset(recording_id)
        self.repository.shift_time(recording_id, started_at.isoformat(), (started_at + duration).isoformat(), TIME_MANUAL)
        return self.get(recording_id)

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
