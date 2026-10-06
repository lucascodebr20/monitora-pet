from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from app.domain.clock import utc_now
from app.domain.errors import EntityConflictError
from app.infra.database.database import Database

COLUMNS = "id, camera_id, path, created_at, last_scanned_at"


class WatchedFolderRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, camera_id: str, path: str) -> dict[str, Any]:
        folder_id = str(uuid4())
        try:
            self.database.execute(
                f"INSERT INTO watched_folders ({COLUMNS}) VALUES (?, ?, ?, ?, NULL)",
                (folder_id, camera_id, path, utc_now()),
            )
        except sqlite3.IntegrityError as exc:
            raise EntityConflictError("Esta pasta já está vigiada para a câmera.") from exc
        return self.get(folder_id) or {}

    def get(self, folder_id: str) -> dict[str, Any] | None:
        return self.database.one(f"SELECT {COLUMNS} FROM watched_folders WHERE id = ?", (folder_id,))

    def list(self, camera_id: str | None = None) -> list[dict[str, Any]]:
        if camera_id:
            return self.database.all(
                f"SELECT {COLUMNS} FROM watched_folders WHERE camera_id = ? ORDER BY created_at", (camera_id,)
            )
        return self.database.all(f"SELECT {COLUMNS} FROM watched_folders ORDER BY created_at")

    def mark_scanned(self, folder_id: str) -> None:
        self.database.execute("UPDATE watched_folders SET last_scanned_at = ? WHERE id = ?", (utc_now(), folder_id))

    def delete(self, folder_id: str) -> None:
        self.database.execute("DELETE FROM watched_folders WHERE id = ?", (folder_id,))
