from __future__ import annotations

from typing import Any

from app.infra.database.database import Database


class EventRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(
        self,
        camera_id: str | None = None,
        zone_id: str | None = None,
        date: str | None = None,
        pending_review: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        parameters: list[Any] = []
        if camera_id:
            filters.append("e.camera_id = ?")
            parameters.append(camera_id)
        if zone_id:
            filters.append("e.zone_id = ?")
            parameters.append(zone_id)
        if date:
            filters.append("substr(e.started_at, 1, 10) = ?")
            parameters.append(date)
        if pending_review:
            filters.append("NOT EXISTS (SELECT 1 FROM human_reviews hr WHERE hr.event_id = e.id)")
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        parameters.append(limit)
        return self.database.all(
            f"""SELECT e.*, c.name AS camera_name, z.name AS zone_name, z.type AS zone_type,
                       (SELECT decision FROM human_reviews r WHERE r.event_id = e.id
                        ORDER BY created_at DESC LIMIT 1) AS review_decision
                FROM events e JOIN cameras c ON c.id = e.camera_id JOIN zones z ON z.id = e.zone_id
                {where} ORDER BY e.started_at DESC LIMIT ?""",
            tuple(parameters),
        )

    def exists(self, event_id: str) -> bool:
        return self.database.one("SELECT id FROM events WHERE id = ?", (event_id,)) is not None

    def create_review(self, review: dict[str, Any]) -> None:
        self.database.execute(
            """INSERT INTO human_reviews
               (id, event_id, decision, corrected_activity, cat_name, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            tuple(review[key] for key in ("id", "event_id", "decision", "corrected_activity", "cat_name", "notes", "created_at")),
        )

    def count_on_date(self, date: str) -> int:
        row = self.database.one(
            "SELECT COUNT(*) AS total FROM events WHERE substr(started_at, 1, 10) = ?", (date,)
        )
        return int(row["total"]) if row else 0

    def count_pending_reviews(self) -> int:
        row = self.database.one(
            """SELECT COUNT(*) AS total FROM events e
               WHERE NOT EXISTS (SELECT 1 FROM human_reviews r WHERE r.event_id = e.id)"""
        )
        return int(row["total"]) if row else 0

    def count_by_zone_type_on_date(self, date: str) -> dict[str, int]:
        rows = self.database.all(
            """SELECT z.type, COUNT(e.id) AS total FROM zones z
               LEFT JOIN events e ON e.zone_id = z.id AND substr(e.started_at, 1, 10) = ?
               GROUP BY z.type""",
            (date,),
        )
        return {row["type"]: int(row["total"]) for row in rows}
