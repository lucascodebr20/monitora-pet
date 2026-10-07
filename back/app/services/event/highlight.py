from __future__ import annotations

from typing import Any

from app.domain.errors import EntityNotFoundError
from app.infra.repositories.event_highlight_repository import EventHighlightRepository
from app.infra.repositories.event_repository import EventRepository


class EventHighlightService:
    def __init__(self, events: EventRepository, highlights: EventHighlightRepository) -> None:
        self.events = events
        self.highlights = highlights

    def set_highlighted(self, event_id: str, highlighted: bool) -> dict[str, Any]:
        if not self.events.exists(event_id):
            raise EntityNotFoundError("Evento não encontrado.")
        if highlighted:
            self.highlights.add(event_id)
        else:
            self.highlights.remove(event_id)
        return self.events.find(event_id)
