from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.domain.clock import utc_now
from app.infra.database.database import Database


class MonitoringSessionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def open(self, camera_id: str, started_at: datetime) -> str:
        session_id = str(uuid4())
        stamp = started_at.isoformat()
        self.database.execute(
            """INSERT INTO monitoring_sessions (id, camera_id, started_at, ended_at, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, camera_id, stamp, stamp, utc_now()),
        )
        return session_id

    def extend(self, session_id: str, ended_at: datetime) -> None:
        self.database.execute(
            "UPDATE monitoring_sessions SET ended_at = ? WHERE id = ? AND ended_at < ?",
            (ended_at.isoformat(), session_id, ended_at.isoformat()),
        )

    def covered_intervals(self, camera_id: str, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        rows = self.database.all(
            """SELECT started_at, ended_at FROM monitoring_sessions
               WHERE camera_id = ? AND ended_at > ? AND started_at < ?
               ORDER BY started_at""",
            (camera_id, start.isoformat(), end.isoformat()),
        )
        return [(datetime.fromisoformat(row["started_at"]), datetime.fromisoformat(row["ended_at"])) for row in rows]
