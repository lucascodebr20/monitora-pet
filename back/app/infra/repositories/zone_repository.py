from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.domain.clock import utc_now
from app.infra.database.database import Database

ZONE_COLUMNS = (
    "id, camera_id, name, type, polygon, minimum_presence_seconds, absence_tolerance_seconds, "
    "cooldown_seconds, enabled, created_at, updated_at"
)


class ZoneRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        zone_id = str(uuid4())
        now = utc_now()
        self.database.execute(
            """INSERT INTO zones
               (id, camera_id, name, type, polygon, minimum_presence_seconds,
                absence_tolerance_seconds, cooldown_seconds, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                zone_id, values["camera_id"], values["name"], values["type"],
                self._serialize_polygon(values["polygon"]), values.get("minimum_presence_seconds", 3),
                values.get("absence_tolerance_seconds", 1), values.get("cooldown_seconds", 10),
                int(values.get("enabled", True)), now, now,
            ),
        )
        return self.get(zone_id) or {}

    def get(self, zone_id: str) -> dict[str, Any] | None:
        zone = self.database.one(f"SELECT {ZONE_COLUMNS} FROM zones WHERE id = ?", (zone_id,))
        if zone:
            zone["polygon"] = self._deserialize_polygon(zone["polygon"])
        return zone

    def list(self, camera_id: str | None = None) -> list[dict[str, Any]]:
        sql = f"SELECT {ZONE_COLUMNS} FROM zones"
        parameters: tuple[Any, ...] = ()
        if camera_id:
            sql += " WHERE camera_id = ?"
            parameters = (camera_id,)
        sql += " ORDER BY created_at"
        zones = self.database.all(sql, parameters)
        for zone in zones:
            zone["polygon"] = self._deserialize_polygon(zone["polygon"])
        return zones

    def delete(self, zone_id: str) -> None:
        self.database.execute("DELETE FROM zones WHERE id = ?", (zone_id,))

    def update(self, zone_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self.database.execute(
            """UPDATE zones SET name = ?, type = ?, polygon = ?, minimum_presence_seconds = ?,
               absence_tolerance_seconds = ?, cooldown_seconds = ?, updated_at = ? WHERE id = ?""",
            (
                values["name"], values["type"], self._serialize_polygon(values["polygon"]),
                values["minimum_presence_seconds"], values["absence_tolerance_seconds"],
                values["cooldown_seconds"], utc_now(), zone_id,
            ),
        )
        return self.get(zone_id) or {}

    def _serialize_polygon(self, polygon: Any) -> str:
        return json.dumps([{"x": float(point[0]), "y": float(point[1])} for point in polygon])

    def _deserialize_polygon(self, value: str) -> list[dict[str, float]]:
        points = json.loads(value)
        return [
            {"x": float(point["x"]), "y": float(point["y"])}
            if isinstance(point, dict)
            else {"x": float(point[0]), "y": float(point[1])}
            for point in points
        ]
