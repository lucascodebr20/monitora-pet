from datetime import datetime, timedelta, timezone
from typing import Any

from app.infra.repositories.notice_repository import NoticeRepository


class NoticeService:
    def __init__(self, repository: NoticeRepository) -> None:
        self.repository = repository

    def active(self) -> list[dict[str, Any]]:
        active: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for rule in self.repository.list_enabled():
            last_at = self.repository.last_event_at(rule["zone_type"])
            threshold = now - timedelta(hours=rule["max_hours_without_event"])
            if not last_at or datetime.fromisoformat(last_at) < threshold:
                active.append({**rule, "last_event_at": last_at})
        return active
