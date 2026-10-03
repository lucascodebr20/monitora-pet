from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.infra.database.database import Database, utc_now


class PetRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(self) -> list[dict[str, Any]]:
        return self.database.all(
            """SELECT p.*, COUNT(DISTINCT e.id) AS event_count,
                      COUNT(DISTINCT r.id) AS reference_count
               FROM pets p
               LEFT JOIN events e ON e.pet_id = p.id
               LEFT JOIN pet_reference_images r ON r.pet_id = p.id
               GROUP BY p.id ORDER BY p.name COLLATE NOCASE"""
        )

    def get(self, pet_id: str) -> dict[str, Any] | None:
        return self.database.one("SELECT * FROM pets WHERE id = ?", (pet_id,))

    def create(self, name: str, species: str, description: str, photo_path: str | None) -> dict[str, Any]:
        pet_id = str(uuid4())
        now = utc_now()
        self.database.execute(
            """INSERT INTO pets (id, name, species, description, photo_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pet_id, name, species, description, photo_path, now, now),
        )
        return self.get(pet_id) or {}

    def update(self, pet_id: str, name: str, species: str, description: str, photo_path: str | None) -> dict[str, Any]:
        self.database.execute(
            """UPDATE pets SET name = ?, species = ?, description = ?,
               photo_path = COALESCE(?, photo_path), updated_at = ? WHERE id = ?""",
            (name, species, description, photo_path, utc_now(), pet_id),
        )
        return self.get(pet_id) or {}

    def delete(self, pet_id: str) -> None:
        self.database.execute("DELETE FROM pets WHERE id = ?", (pet_id,))

    def has_history(self, pet_id: str) -> bool:
        return self.database.one(
            """SELECT id FROM events WHERE pet_id = ?
               UNION SELECT id FROM pet_reference_images WHERE pet_id = ? LIMIT 1""",
            (pet_id, pet_id),
        ) is not None

    def create_reference_image(self, pet_id: str, event_id: str, image_path: str) -> dict[str, str]:
        image_id = str(uuid4())
        self.database.execute(
            """INSERT INTO pet_reference_images (id, pet_id, event_id, image_path, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (image_id, pet_id, event_id, image_path, utc_now()),
        )
        return {"id": image_id, "pet_id": pet_id, "event_id": event_id, "image_path": image_path}

    def list_reference_images(self, pet_id: str) -> list[dict[str, Any]]:
        return self.database.all(
            """SELECT id, pet_id, event_id, image_path, created_at
               FROM pet_reference_images WHERE pet_id = ? ORDER BY created_at DESC""",
            (pet_id,),
        )
