from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from app.domain.clock import utc_now
from app.domain.errors import EntityConflictError, OperationFailedError
from app.infra.database.database import Database

CAMERA_COLUMNS = "id, name, ip, manufacturer, model, onvif_port, rtsp_url, enabled, created_at, updated_at"


class CameraRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        camera_id = str(uuid4())
        now = utc_now()
        try:
            self.database.execute(
                f"""INSERT INTO cameras ({CAMERA_COLUMNS})
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    camera_id, values["name"], values["ip"], values.get("manufacturer", ""),
                    values.get("model", ""), values.get("onvif_port", 8899), values.get("rtsp_url"),
                    int(values.get("enabled", True)), now, now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise EntityConflictError("Já existe uma câmera cadastrada com esse IP.") from exc
        camera = self.get(camera_id)
        if camera is None:
            raise OperationFailedError("A câmera foi gravada mas não pôde ser lida de volta.")
        return camera

    def get(self, camera_id: str) -> dict[str, Any] | None:
        return self.database.one(f"SELECT {CAMERA_COLUMNS} FROM cameras WHERE id = ?", (camera_id,))

    def list(self) -> list[dict[str, Any]]:
        return self.database.all(f"SELECT {CAMERA_COLUMNS} FROM cameras ORDER BY created_at")

    def delete(self, camera_id: str) -> None:
        self.database.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
