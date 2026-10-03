from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.infra.database.database import Database, utc_now


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
            filters.append("e.ended_at IS NOT NULL")
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        parameters.append(limit)
        return self.database.all(
            f"""SELECT e.*, c.name AS camera_name, z.name AS zone_name, z.type AS zone_type,
                       (SELECT decision FROM human_reviews r WHERE r.event_id = e.id
                        ORDER BY created_at DESC LIMIT 1) AS review_decision,
                       p.name AS pet_name
                FROM events e JOIN cameras c ON c.id = e.camera_id JOIN zones z ON z.id = e.zone_id
                LEFT JOIN pets p ON p.id = e.pet_id
                {where} ORDER BY e.started_at DESC LIMIT ?""",
            tuple(parameters),
        )

    def exists(self, event_id: str) -> bool:
        return self.database.one("SELECT id FROM events WHERE id = ?", (event_id,)) is not None

    def get(self, event_id: str) -> dict[str, Any] | None:
        return self.database.one("SELECT * FROM events WHERE id = ?", (event_id,))

    def create_review(self, review: dict[str, Any]) -> None:
        self.database.execute(
            """INSERT INTO human_reviews
               (id, event_id, decision, corrected_activity, cat_name, notes, created_at, pet_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(review.get(key) for key in ("id", "event_id", "decision", "corrected_activity", "cat_name", "notes", "created_at", "pet_id")),
        )

    def assign_pet(self, event_id: str, pet_id: str | None) -> None:
        self.database.execute("UPDATE events SET pet_id = ? WHERE id = ?", (pet_id, event_id))

    def create_detected_event(
        self,
        camera_id: str,
        zone_id: str,
        started_at: str,
        confirmed_at: str,
        confidence: float,
        snapshot_path: str | None,
        species: str,
        pet_capture_path: str | None,
    ) -> str:
        event_id = str(uuid4())
        self.database.execute(
            """INSERT INTO events
               (id, camera_id, zone_id, started_at, confirmed_at, confidence,
                activity, snapshot_path, engine_version, created_at, detected_species, pet_capture_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id, camera_id, zone_id, started_at, confirmed_at, confidence,
                "NEAR_ZONE", snapshot_path, "2", utc_now(), species, pet_capture_path,
            ),
        )
        return event_id

    def finish_detected_event(self, event_id: str, ended_at: str, duration: float, reason: str) -> None:
        self.database.execute(
            """UPDATE events SET ended_at = ?, duration_seconds = ?, end_reason = ?
               WHERE id = ? AND ended_at IS NULL""",
            (ended_at, duration, reason, event_id),
        )

    def attach_clip(self, event_id: str, clip_path: str) -> None:
        self.database.execute(
            "UPDATE events SET clip_path = ? WHERE id = ?",
            (clip_path, event_id),
        )

    def finish_open_events(self, ended_at: str) -> None:
        self.database.execute(
            """UPDATE events SET ended_at = ?, end_reason = 'APPLICATION_RESTART',
               duration_seconds = MAX(0, (julianday(?) - julianday(started_at)) * 86400)
               WHERE ended_at IS NULL""",
            (ended_at, ended_at),
        )

    def count_on_date(self, date: str) -> int:
        row = self.database.one(
            "SELECT COUNT(*) AS total FROM events WHERE substr(started_at, 1, 10) = ?", (date,)
        )
        return int(row["total"]) if row else 0

    def count_pending_reviews(self) -> int:
        row = self.database.one(
            """SELECT COUNT(*) AS total FROM events e
               WHERE e.ended_at IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM human_reviews r WHERE r.event_id = e.id)"""
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
