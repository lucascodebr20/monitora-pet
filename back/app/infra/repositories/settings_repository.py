from __future__ import annotations

import json
from typing import Any

from app.domain.clock import utc_now
from app.infra.database.database import Database


class SettingsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, key: str, default: Any = None) -> Any:
        row = self.database.one("SELECT value FROM app_settings WHERE key = ?", (key,))
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except ValueError:
            return default

    def set(self, key: str, value: Any) -> None:
        self.database.execute(
            """INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, json.dumps(value), utc_now()),
        )

    def all(self) -> dict[str, Any]:
        rows = self.database.all("SELECT key, value FROM app_settings")
        result: dict[str, Any] = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except ValueError:
                continue
        return result
