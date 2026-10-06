from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.domain.clock import utc_now
from app.infra.database.database import Database

RECORDING_COLUMNS = (
    "id, camera_id, origin, path, fingerprint, size_bytes, started_at, ended_at, status, "
    "processed_seconds, error, created_at, processed_at, time_source"
)


class RecordingRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        recording_id = str(uuid4())
        self.database.execute(
            f"""INSERT INTO recordings ({RECORDING_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, NULL, ?, NULL, ?)""",
            (
                recording_id, values["camera_id"], values["origin"], values["path"], values["fingerprint"],
                int(values.get("size_bytes", 0)), values["started_at"], values["ended_at"], utc_now(),
                values.get("time_source", "PROTOCOL"),
            ),
        )
        return self.get(recording_id) or {}

    def get(self, recording_id: str) -> dict[str, Any] | None:
        return self.database.one(f"SELECT {RECORDING_COLUMNS} FROM recordings WHERE id = ?", (recording_id,))

    def find_by_fingerprint(self, camera_id: str, fingerprint: str) -> dict[str, Any] | None:
        return self.database.one(
            f"SELECT {RECORDING_COLUMNS} FROM recordings WHERE camera_id = ? AND fingerprint = ?",
            (camera_id, fingerprint),
        )

    def list(self, camera_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        filters: list[str] = []
        parameters: list[Any] = []
        if camera_id:
            filters.append("camera_id = ?")
            parameters.append(camera_id)
        if status:
            filters.append("status = ?")
            parameters.append(status)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        return self.database.all(
            f"SELECT {RECORDING_COLUMNS} FROM recordings {where} ORDER BY started_at, created_at", tuple(parameters)
        )

    def pending_camera_ids(self) -> list[str]:
        rows = self.database.all(
            "SELECT DISTINCT camera_id FROM recordings WHERE status = 'PENDING' ORDER BY camera_id"
        )
        return [row["camera_id"] for row in rows]

    def set_status(self, recording_id: str, status: str, error: str | None = None) -> None:
        processed_at = utc_now() if status in ("DONE", "FAILED", "SKIPPED") else None
        self.database.execute(
            "UPDATE recordings SET status = ?, error = ?, processed_at = ? WHERE id = ?",
            (status, error, processed_at, recording_id),
        )

    def reset(self, recording_id: str) -> None:
        self.database.execute(
            """UPDATE recordings SET status = 'PENDING', error = NULL, processed_seconds = 0, processed_at = NULL
               WHERE id = ?""",
            (recording_id,),
        )

    def update_progress(self, recording_id: str, processed_seconds: float) -> None:
        self.database.execute(
            "UPDATE recordings SET processed_seconds = ? WHERE id = ?", (processed_seconds, recording_id)
        )

    def shift_time(self, recording_id: str, started_at: str, ended_at: str, time_source: str) -> None:
        self.database.execute(
            "UPDATE recordings SET started_at = ?, ended_at = ?, time_source = ? WHERE id = ?",
            (started_at, ended_at, time_source, recording_id),
        )

    def delete(self, recording_id: str) -> None:
        self.database.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
