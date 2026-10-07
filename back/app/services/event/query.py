from __future__ import annotations

from datetime import date as Date
from typing import Any

from app.domain.errors import InvalidDomainValueError
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
        start_date: str | None = None,
        end_date: str | None = None,
        highlighted: bool = False,
    ) -> dict[str, Any]:
        try:
            parsed_start = Date.fromisoformat(start_date) if start_date else None
            parsed_end = Date.fromisoformat(end_date) if end_date else None
        except ValueError as error:
            raise InvalidDomainValueError("Informe datas válidas para filtrar o histórico.") from error
        if parsed_start and parsed_end and parsed_start > parsed_end:
            raise InvalidDomainValueError("A data inicial não pode ser posterior à data final.")
        events, total = self.repository.search(
            page=page,
            page_size=page_size,
            pet_id=pet_id,
            zone_type=zone_type.value if zone_type else None,
            pending_review=pending_review,
            camera_id=camera_id,
            zone_id=zone_id,
            date=date,
            start_date=start_date,
            end_date=end_date,
            highlighted=highlighted,
        )
        return {"events": events, "total": total, "page": page, "page_size": page_size}
