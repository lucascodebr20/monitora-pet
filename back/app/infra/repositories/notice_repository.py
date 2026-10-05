from __future__ import annotations

from typing import Any

from app.infra.database.database import Database

NOTICE_COLUMNS = "id, zone_type, max_hours_without_event, repeat_hours, enabled, created_at, updated_at"


class NoticeRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_enabled(self) -> list[dict[str, Any]]:
        return self.database.all(f"SELECT {NOTICE_COLUMNS} FROM notice_rules WHERE enabled = 1")

    def last_event_at(self, zone_type: str) -> str | None:
        row = self.database.one(
            """SELECT MAX(e.started_at) AS last_at FROM events e
               JOIN zones z ON z.id = e.zone_id WHERE z.type = ?""",
            (zone_type,),
        )
        return row["last_at"] if row else None
