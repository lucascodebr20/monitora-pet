from __future__ import annotations

from typing import Any

from app.domain.enums import ZoneType
from app.infra.repositories.event_repository import EventRepository


class EventQueryService:
    def __init__(self, repository: EventRepository) -> None:
        self.repository = repository

    def list(
        self,
        camera_id: str | None = None,
        zone_id: str | None = None,
        date: str | None = None,
        pending_review: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.repository.list(camera_id, zone_id, date, pending_review, limit)

    def search(
        self,
        page: int,
        page_size: int,
        pet_id: str | None = None,
        zone_type: ZoneType | None = None,
        pending_review: bool = False,
        camera_id: str | None = None,
        zone_id: str | None = None,
        date: str | None = None,
    ) -> dict[str, Any]:
        events, total = self.repository.search(
            page, page_size, pet_id, zone_type.value if zone_type else None, pending_review,
            camera_id, zone_id, date,
        )
        return {"events": events, "total": total, "page": page, "page_size": page_size}
