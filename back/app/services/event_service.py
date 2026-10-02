from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from app.domain.errors import EntityNotFoundError
from app.infra.database.database import utc_now
from app.infra.repositories.event_repository import EventRepository
from app.services.commands import ReviewEventCommand


class EventService:
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

    def review(self, event_id: str, request: ReviewEventCommand) -> dict[str, Any]:
        if not self.repository.exists(event_id):
            raise EntityNotFoundError("Evento não encontrado.")
        review = {
            "id": str(uuid4()),
            "event_id": event_id,
            **asdict(request),
            "created_at": utc_now(),
        }
        self.repository.create_review(review)
        return review
