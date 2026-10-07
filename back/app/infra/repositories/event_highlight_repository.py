from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.domain.clock import utc_now
from app.infra.database.database import Database


class EventHighlightRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, event_id: str) -> None:
        self.database.execute(
            "INSERT OR IGNORE INTO event_highlights (id, event_id, created_at) VALUES (?, ?, ?)",
            (str(uuid4()), event_id, utc_now()),
        )

    def remove(self, event_id: str) -> None:
        self.database.execute("DELETE FROM event_highlights WHERE event_id = ?", (event_id,))

    def get(self, event_id: str) -> dict[str, Any] | None:
        return self.database.one("SELECT * FROM event_highlights WHERE event_id = ?", (event_id,))
