from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.infra.database.database import Database, utc_now


class CameraRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        camera_id = str(uuid4())
        now = utc_now()
        self.database.execute(
            """INSERT INTO cameras
               (id, name, ip, manufacturer, model, onvif_port, rtsp_url, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                camera_id, values["name"], values["ip"], values.get("manufacturer", ""),
                values.get("model", ""), values.get("onvif_port", 8899), values.get("rtsp_url"),
                int(values.get("enabled", True)), now, now,
            ),
        )
        return self.get(camera_id) or {}

    def get(self, camera_id: str) -> dict[str, Any] | None:
        return self.database.one("SELECT * FROM cameras WHERE id = ?", (camera_id,))

    def list(self) -> list[dict[str, Any]]:
        return self.database.all("SELECT * FROM cameras ORDER BY created_at")

    def delete(self, camera_id: str) -> None:
        self.database.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
