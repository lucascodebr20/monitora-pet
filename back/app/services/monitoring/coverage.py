from __future__ import annotations

from datetime import datetime

from app.infra.repositories.monitoring_session_repository import MonitoringSessionRepository

HEARTBEAT_SECONDS = 15.0


class CoverageRecorder:
    def __init__(self, repository: MonitoringSessionRepository) -> None:
        self.repository = repository
        self._open: dict[str, tuple[str, datetime, datetime]] = {}

    def observe(self, camera_id: str, at: datetime) -> None:
        current = self._open.get(camera_id)
        if current is None:
            self._open[camera_id] = (self.repository.open(camera_id, at), at, at)
            return
        session_id, written_at, _ = current
        if (at - written_at).total_seconds() >= HEARTBEAT_SECONDS:
            self.repository.extend(session_id, at)
            written_at = at
        self._open[camera_id] = (session_id, written_at, at)

    def close(self, camera_id: str) -> None:
        current = self._open.pop(camera_id, None)
        if current:
            session_id, _, last_seen = current
            self.repository.extend(session_id, last_seen)

    def close_all(self) -> None:
        for camera_id in list(self._open):
            self.close(camera_id)
