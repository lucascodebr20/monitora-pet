from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.domain.clock import utc_bounds_for_local_date, utc_now
from app.infra.database.database import Database


EVENT_PROJECTION = """
    SELECT e.*, c.name AS camera_name, z.name AS zone_name,
           COALESCE(e.corrected_zone_type, z.type) AS zone_type,
           (SELECT decision FROM human_reviews r WHERE r.event_id = e.id
            ORDER BY created_at DESC LIMIT 1) AS review_decision,
           p.name AS pet_name
    FROM events e JOIN cameras c ON c.id = e.camera_id JOIN zones z ON z.id = e.zone_id
    LEFT JOIN pets p ON p.id = e.pet_id
"""
PENDING_REVIEW_FILTERS = (
    "NOT EXISTS (SELECT 1 FROM human_reviews hr WHERE hr.event_id = e.id)",
    "e.ended_at IS NOT NULL",
)


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
        where, parameters = self._filters(camera_id=camera_id, zone_id=zone_id, date=date, pending_review=pending_review)
        return self.database.all(
            f"{EVENT_PROJECTION} {where} ORDER BY e.started_at DESC LIMIT ?", (*parameters, limit)
        )

    def search(
        self,
        page: int,
        page_size: int,
        pet_id: str | None = None,
        zone_type: str | None = None,
        pending_review: bool = False,
        camera_id: str | None = None,
        zone_id: str | None = None,
        date: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        where, parameters = self._filters(
            camera_id=camera_id, zone_id=zone_id, date=date, pending_review=pending_review,
            pet_id=pet_id, zone_type=zone_type,
        )
        total_row = self.database.one(
            f"SELECT COUNT(*) AS total FROM events e JOIN zones z ON z.id = e.zone_id {where}", tuple(parameters)
        )
        total = int(total_row["total"]) if total_row else 0
        rows = self.database.all(
            f"{EVENT_PROJECTION} {where} ORDER BY e.started_at DESC LIMIT ? OFFSET ?",
            (*parameters, page_size, (page - 1) * page_size),
        )
        return rows, total

    @staticmethod
    def _filters(
        camera_id: str | None = None,
        zone_id: str | None = None,
        date: str | None = None,
        pending_review: bool = False,
        pet_id: str | None = None,
        zone_type: str | None = None,
    ) -> tuple[str, list[Any]]:
        filters: list[str] = []
        parameters: list[Any] = []
        if pet_id:
            filters.append("e.pet_id = ?")
            parameters.append(pet_id)
        if zone_type:
            filters.append("COALESCE(e.corrected_zone_type, z.type) = ?")
            parameters.append(zone_type)
        if camera_id:
            filters.append("e.camera_id = ?")
            parameters.append(camera_id)
        if zone_id:
            filters.append("e.zone_id = ?")
            parameters.append(zone_id)
        if date:
            start, end = utc_bounds_for_local_date(date)
            filters.append("e.started_at >= ? AND e.started_at < ?")
            parameters.extend((start, end))
        if pending_review:
            filters.extend(PENDING_REVIEW_FILTERS)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        return where, parameters

    def exists(self, event_id: str) -> bool:
        return self.database.one("SELECT id FROM events WHERE id = ?", (event_id,)) is not None

    def has_review(self, event_id: str) -> bool:
        return self.database.one("SELECT id FROM human_reviews WHERE event_id = ? LIMIT 1", (event_id,)) is not None

    def get(self, event_id: str) -> dict[str, Any] | None:
        return self.database.one(
            """SELECT e.*, COALESCE(e.corrected_zone_type, z.type) AS zone_type
               FROM events e JOIN zones z ON z.id = e.zone_id WHERE e.id = ?""",
            (event_id,),
        )

    def complete_review(self, review: dict[str, Any], pet_id: str | None, corrected_zone_type: str | None) -> None:
        zone_type = corrected_zone_type
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO human_reviews
                   (id, event_id, decision, corrected_activity, cat_name, notes, created_at, pet_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(review.get(key) for key in ("id", "event_id", "decision", "corrected_activity", "cat_name", "notes", "created_at", "pet_id")),
            )
            connection.execute(
                """UPDATE events SET pet_id = ?,
                   corrected_zone_type = COALESCE(?, corrected_zone_type)
                   WHERE id = ?""",
                (pet_id, zone_type, review["event_id"]),
            )
            if pet_id:
                connection.execute(
                    """INSERT INTO pet_reference_images (id, pet_id, event_id, image_path, created_at)
                       SELECT ?, ?, id, pet_capture_path, ? FROM events
                       WHERE id = ? AND pet_capture_path IS NOT NULL""",
                    (str(uuid4()), pet_id, review["created_at"], review["event_id"]),
                )

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
        pet_id: str | None = None,
        identification_confidence: float | None = None,
        identification_method: str | None = None,
    ) -> str:
        event_id = str(uuid4())
        self.database.execute(
            """INSERT INTO events
               (id, camera_id, zone_id, started_at, confirmed_at, confidence,
                activity, snapshot_path, engine_version, created_at, detected_species, pet_capture_path,
                pet_id, automatically_identified_pet_id, pet_identification_confidence,
                pet_identification_method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id, camera_id, zone_id, started_at, confirmed_at, confidence,
                "NEAR_ZONE", snapshot_path, "3", utc_now(), species, pet_capture_path,
                pet_id, pet_id, identification_confidence, identification_method,
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
        start, end = utc_bounds_for_local_date(date)
        row = self.database.one(
            """SELECT COUNT(*) AS total FROM events e
               WHERE e.started_at >= ? AND e.started_at < ?
               AND NOT EXISTS (SELECT 1 FROM human_reviews r
                               WHERE r.event_id = e.id AND r.decision = 'FALSE_POSITIVE')""",
            (start, end),
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
        start, end = utc_bounds_for_local_date(date)
        rows = self.database.all(
            """SELECT COALESCE(e.corrected_zone_type, z.type) AS type, COUNT(e.id) AS total
               FROM zones z LEFT JOIN events e ON e.zone_id = z.id
                   AND e.started_at >= ? AND e.started_at < ?
                   AND NOT EXISTS (SELECT 1 FROM human_reviews r
                                   WHERE r.event_id = e.id AND r.decision = 'FALSE_POSITIVE')
               GROUP BY COALESCE(e.corrected_zone_type, z.type)""",
            (start, end),
        )
        return {row["type"]: int(row["total"]) for row in rows}
