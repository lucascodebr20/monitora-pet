from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from app.domain.errors import InvalidDomainValueError
from app.infra.media.media_cleanup import MediaCleanup
from app.infra.media.recording_reader import index_path_for
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.recording_repository import RecordingRepository
from app.infra.repositories.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)

RETENTION_KEY = "retention_days"
DEFAULT_RETENTION_DAYS = 7
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 365


@dataclass(frozen=True)
class RetentionResult:
    media_removed: int
    recordings_removed: int
    cutoff: str


class MediaRetentionService:
    def __init__(
        self,
        settings: SettingsRepository,
        event_repository: EventRepository,
        recording_repository: RecordingRepository,
        cleanup: MediaCleanup,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.settings = settings
        self.event_repository = event_repository
        self.recording_repository = recording_repository
        self.cleanup = cleanup
        self._now = now

    def retention_days(self) -> int:
        value = self.settings.get(RETENTION_KEY, DEFAULT_RETENTION_DAYS)
        try:
            return max(MIN_RETENTION_DAYS, min(MAX_RETENTION_DAYS, int(value)))
        except (TypeError, ValueError):
            return DEFAULT_RETENTION_DAYS

    def set_retention_days(self, days: int) -> int:
        if not MIN_RETENTION_DAYS <= days <= MAX_RETENTION_DAYS:
            raise InvalidDomainValueError(f"A retenção deve ficar entre {MIN_RETENTION_DAYS} e {MAX_RETENTION_DAYS} dias.")
        self.settings.set(RETENTION_KEY, days)
        return days

    def view(self) -> dict[str, int]:
        return {"retention_days": self.retention_days()}

    def run(self) -> RetentionResult:
        cutoff = self._now() - timedelta(days=self.retention_days())
        cutoff_iso = cutoff.isoformat()
        media_removed = self.cleanup.remove(self.event_repository.expire_media(cutoff_iso))
        recordings_removed = 0
        for recording in self.recording_repository.expired(cutoff_iso):
            path = Path(recording["path"])
            if not self.cleanup.owns(path) or not path.exists():
                continue
            recordings_removed += self.cleanup.remove([path, index_path_for(path)]) and 1
        if media_removed or recordings_removed:
            logger.info("Retenção: %d mídias e %d gravações removidas antes de %s", media_removed, recordings_removed, cutoff_iso)
        return RetentionResult(media_removed, recordings_removed, cutoff_iso)
