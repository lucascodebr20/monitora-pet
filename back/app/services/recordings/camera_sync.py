from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.domain.errors import EntityNotFoundError, OperationFailedError
from app.domain.intervals import subtract_intervals
from app.infra.camera import onvif
from app.infra.camera.rtsp_replay import ReplayDownloader, ReplayError
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.repositories.monitoring_session_repository import MonitoringSessionRepository
from app.infra.repositories.recording_repository import RecordingRepository
from app.services.camera.profile import SUPPORT_ONVIF_REPLAY, CameraProfileService
from app.services.recordings.importer import ORIGIN_CAMERA, RecordingImportService

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK = timedelta(hours=24)
MAX_CHUNK = timedelta(hours=1)
MIN_CHUNK_SECONDS = 2.0


@dataclass
class CameraSyncResult:
    downloaded: list[dict[str, Any]] = field(default_factory=list)
    skipped_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


class CameraRecordingSync:
    def __init__(
        self,
        camera_repository: CameraRepository,
        session_repository: MonitoringSessionRepository,
        recording_repository: RecordingRepository,
        profile: CameraProfileService,
        importer: RecordingImportService,
        recordings_dir: Path,
        downloader: ReplayDownloader | None = None,
        find_recordings: Callable[..., list[onvif.RecordingSpan]] = onvif.find_recordings,
        recording_services: Callable[..., dict[str, str]] = onvif.recording_services,
        replay_uri: Callable[..., str | None] = onvif.replay_uri,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.camera_repository = camera_repository
        self.session_repository = session_repository
        self.recording_repository = recording_repository
        self.profile = profile
        self.importer = importer
        self.recordings_dir = recordings_dir
        self.downloader = downloader or ReplayDownloader()
        self._find_recordings = find_recordings
        self._recording_services = recording_services
        self._replay_uri = replay_uri
        self._now = now

    def sync(self, camera_id: str, since: datetime | None = None, until: datetime | None = None) -> CameraSyncResult:
        camera = self.camera_repository.get(camera_id)
        if not camera:
            raise EntityNotFoundError("Câmera não encontrada.")
        if camera["recording_support"] != SUPPORT_ONVIF_REPLAY:
            raise OperationFailedError("Esta câmera não oferece download de gravações pela rede.")
        username, password = self.profile.credentials_for(camera_id)
        services = self._recording_services(camera["ip"], camera["onvif_port"], username, password)
        if not services:
            raise OperationFailedError("A câmera não respondeu aos serviços de gravação ONVIF.")
        until = until or self._now()
        since = since or self._default_since(camera, until)
        offset = timedelta(seconds=float(camera["clock_offset_seconds"] or 0.0))
        result = CameraSyncResult()
        spans = self._find_recordings(services["search"], since + offset, until + offset, username, password)
        for span in spans:
            uri = self._replay_uri(services["replay"], span.token, camera["ip"], username, password)
            if not uri:
                result.errors.append(f"Sem URI de replay para a gravação {span.token}.")
                continue
            for chunk_start, chunk_end in self._chunks(camera_id, span.start - offset, span.end - offset, result):
                self._download_chunk(camera, username, password, uri, chunk_start, chunk_end, offset, result)
        if not result.errors:
            self.camera_repository.mark_synced(camera_id, until.isoformat())
        return result

    def _default_since(self, camera: dict[str, Any], until: datetime) -> datetime:
        if camera.get("last_synced_at"):
            return datetime.fromisoformat(camera["last_synced_at"])
        return until - DEFAULT_LOOKBACK

    def _chunks(
        self, camera_id: str, start: datetime, end: datetime, result: CameraSyncResult
    ) -> list[tuple[datetime, datetime]]:
        covered = self.session_repository.covered_intervals(camera_id, start, end)
        covered.extend(
            (datetime.fromisoformat(item["started_at"]), datetime.fromisoformat(item["ended_at"]))
            for item in self.recording_repository.list(camera_id)
            if item["status"] != "FAILED"
        )
        windows = subtract_intervals(start, end, covered)
        result.skipped_seconds += (end - start).total_seconds() - sum((b - a).total_seconds() for a, b in windows)
        chunks: list[tuple[datetime, datetime]] = []
        for window_start, window_end in windows:
            cursor = window_start
            while cursor < window_end:
                chunk_end = min(cursor + MAX_CHUNK, window_end)
                if (chunk_end - cursor).total_seconds() >= MIN_CHUNK_SECONDS:
                    chunks.append((cursor, chunk_end))
                cursor = chunk_end
        return chunks

    def _download_chunk(
        self,
        camera: dict[str, Any],
        username: str,
        password: str,
        uri: str,
        start: datetime,
        end: datetime,
        offset: timedelta,
        result: CameraSyncResult,
    ) -> None:
        destination = self.recordings_dir / camera["id"] / f"{start.strftime('%Y%m%dT%H%M%SZ')}.h264"
        try:
            replay = self.downloader.download(uri, username, password, start + offset, end + offset, destination)
        except (ReplayError, OSError) as error:
            logger.warning("Falha ao baixar gravação da câmera %s entre %s e %s: %s", camera["id"], start, end, error)
            result.errors.append(str(error))
            return
        started_at = (replay.first_timestamp - offset) if replay.first_timestamp else start
        if replay.codec == "h265" and destination.suffix != ".h265":
            renamed = destination.with_suffix(".h265")
            destination.replace(renamed)
            index = destination.with_name(destination.name + ".index.json")
            if index.is_file():
                index.replace(renamed.with_name(renamed.name + ".index.json"))
            destination = renamed
        try:
            result.downloaded.append(self.importer.register(camera["id"], destination, started_at, ORIGIN_CAMERA))
        except OperationFailedError as error:
            result.errors.append(str(error))
