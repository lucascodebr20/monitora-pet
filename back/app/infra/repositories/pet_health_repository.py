from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.domain.clock import utc_now
from app.infra.database.database import Database

TABLES = {
    "food": ("pet_food_periods", "started_on DESC, created_at DESC"),
    "weight": ("pet_weights", "measured_on DESC, created_at DESC"),
    "exam": ("pet_exams", "COALESCE(performed_on, substr(created_at, 1, 10)) DESC, created_at DESC"),
    "treatment": ("pet_treatments", "ended_on IS NOT NULL, started_on DESC, created_at DESC"),
    "dose": ("pet_doses", "given_on DESC, created_at DESC"),
}
UPDATED_AT = {"pet_food_periods", "pet_exams", "pet_treatments"}
ATTACHMENT_COLUMNS = ("id, pet_id, exam_id, entry_id, position, file_path, thumbnail_path, original_name, "
                      "media_type, size_bytes, sha256, created_at")


class PetHealthRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(self, kind: str, pet_id: str) -> list[dict[str, Any]]:
        table, order = TABLES[kind]
        return self.database.all(f"SELECT * FROM {table} WHERE pet_id = ? ORDER BY {order}", (pet_id,))

    def get(self, kind: str, pet_id: str, record_id: str) -> dict[str, Any] | None:
        table, _ = TABLES[kind]
        return self.database.one(f"SELECT * FROM {table} WHERE id = ? AND pet_id = ?", (record_id, pet_id))

    def create(self, kind: str, pet_id: str, values: dict[str, Any]) -> dict[str, Any]:
        table, _ = TABLES[kind]
        now = utc_now()
        row = {"id": str(uuid4()), "pet_id": pet_id, **values, "created_at": now}
        if table in UPDATED_AT:
            row["updated_at"] = now
        columns = ", ".join(row)
        self.database.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({', '.join('?' for _ in row)})", tuple(row.values())
        )
        return self.get(kind, pet_id, row["id"]) or {}

    def update(self, kind: str, pet_id: str, record_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        table, _ = TABLES[kind]
        row = dict(values)
        if table in UPDATED_AT:
            row["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in row)
        self.database.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ? AND pet_id = ?", (*row.values(), record_id, pet_id)
        )
        return self.get(kind, pet_id, record_id)

    def delete(self, kind: str, pet_id: str, record_id: str) -> list[str | None]:
        table, _ = TABLES[kind]
        owner = {"exam": "a.exam_id = ?", "treatment": "e.treatment_id = ?"}.get(kind)
        paths: list[str | None] = []
        if owner:
            for row in self.database.all(
                f"""SELECT a.file_path, a.thumbnail_path FROM pet_health_attachments a
                    LEFT JOIN pet_treatment_entries e ON e.id = a.entry_id
                    WHERE a.pet_id = ? AND {owner}""",
                (pet_id, record_id),
            ):
                paths += [row["file_path"], row["thumbnail_path"]]
        self.database.execute(f"DELETE FROM {table} WHERE id = ? AND pet_id = ?", (record_id, pet_id))
        return paths

    def finish_open_food(self, pet_id: str, ended_on: str) -> None:
        self.database.execute(
            """UPDATE pet_food_periods SET ended_on = ?, updated_at = ?
               WHERE pet_id = ? AND ended_on IS NULL AND started_on <= ?""",
            (ended_on, utc_now(), pet_id, ended_on),
        )

    def list_entries(self, treatment_id: str) -> list[dict[str, Any]]:
        return self.database.all(
            "SELECT * FROM pet_treatment_entries WHERE treatment_id = ? ORDER BY observed_at DESC, created_at DESC",
            (treatment_id,),
        )

    def get_entry(self, pet_id: str, treatment_id: str, entry_id: str) -> dict[str, Any] | None:
        return self.database.one(
            """SELECT e.* FROM pet_treatment_entries e JOIN pet_treatments t ON t.id = e.treatment_id
               WHERE e.id = ? AND e.treatment_id = ? AND t.pet_id = ?""",
            (entry_id, treatment_id, pet_id),
        )

    def create_entry(self, treatment_id: str, observed_at: str, notes: str) -> dict[str, Any]:
        entry_id = str(uuid4())
        self.database.execute(
            """INSERT INTO pet_treatment_entries (id, treatment_id, observed_at, notes, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (entry_id, treatment_id, observed_at, notes, utc_now()),
        )
        return self.database.one("SELECT * FROM pet_treatment_entries WHERE id = ?", (entry_id,)) or {}

    def delete_entry(self, entry_id: str) -> list[str | None]:
        paths: list[str | None] = []
        for row in self.database.all(
            "SELECT file_path, thumbnail_path FROM pet_health_attachments WHERE entry_id = ?", (entry_id,)
        ):
            paths += [row["file_path"], row["thumbnail_path"]]
        self.database.execute("DELETE FROM pet_treatment_entries WHERE id = ?", (entry_id,))
        return paths

    def list_attachments(self, pet_id: str, *, exam_ids: list[str] = (), entry_ids: list[str] = ()) -> list[dict[str, Any]]:
        owners = [("exam_id", exam_ids), ("entry_id", entry_ids)]
        clauses = [f"{column} IN ({', '.join('?' for _ in ids)})" for column, ids in owners if ids]
        if not clauses:
            return []
        parameters = tuple(value for _, ids in owners for value in ids)
        return self.database.all(
            f"""SELECT {ATTACHMENT_COLUMNS} FROM pet_health_attachments
                WHERE pet_id = ? AND ({' OR '.join(clauses)}) ORDER BY position, created_at""",
            (pet_id, *parameters),
        )

    def get_attachment(self, pet_id: str, attachment_id: str) -> dict[str, Any] | None:
        return self.database.one(
            f"SELECT {ATTACHMENT_COLUMNS} FROM pet_health_attachments WHERE id = ? AND pet_id = ?",
            (attachment_id, pet_id),
        )

    def find_attachment_by_hash(self, pet_id: str, sha256: str, *, exam_id: str | None, entry_id: str | None) -> dict[str, Any] | None:
        return self.database.one(
            f"""SELECT {ATTACHMENT_COLUMNS} FROM pet_health_attachments
                WHERE pet_id = ? AND sha256 = ? AND exam_id IS ? AND entry_id IS ?""",
            (pet_id, sha256, exam_id, entry_id),
        )

    def create_attachment(self, pet_id: str, values: dict[str, Any]) -> dict[str, Any]:
        attachment_id = str(uuid4())
        owner_column = "exam_id" if values.get("exam_id") else "entry_id"
        with self.database.connect() as connection:
            position = connection.execute(
                f"SELECT COALESCE(MAX(position) + 1, 0) FROM pet_health_attachments WHERE {owner_column} = ?",
                (values[owner_column],),
            ).fetchone()[0]
            row = {"id": attachment_id, "pet_id": pet_id, "position": position, **values, "created_at": utc_now()}
            connection.execute(
                f"INSERT INTO pet_health_attachments ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
                tuple(row.values()),
            )
        return self.get_attachment(pet_id, attachment_id) or {}

    def delete_attachment(self, pet_id: str, attachment_id: str) -> None:
        self.database.execute("DELETE FROM pet_health_attachments WHERE id = ? AND pet_id = ?", (attachment_id, pet_id))

    def pet_file_paths(self, pet_id: str) -> list[str | None]:
        rows = self.database.all(
            "SELECT file_path, thumbnail_path FROM pet_health_attachments WHERE pet_id = ?", (pet_id,)
        )
        return [path for row in rows for path in (row["file_path"], row["thumbnail_path"])]

    def due_doses(self, until: str) -> list[dict[str, Any]]:
        return self.database.all(
            """SELECT d.*, p.name AS pet_name FROM pet_doses d JOIN pets p ON p.id = d.pet_id
               WHERE d.next_due_on IS NOT NULL AND d.next_due_on <= ?
               AND NOT EXISTS (SELECT 1 FROM pet_doses later
                               WHERE later.pet_id = d.pet_id AND later.kind = d.kind
                               AND lower(trim(later.name)) = lower(trim(d.name))
                               AND later.given_on > d.given_on)
               ORDER BY d.next_due_on, p.name COLLATE NOCASE""",
            (until,),
        )

    def camera_events(self, pet_id: str, start: str, end: str) -> list[dict[str, Any]]:
        return self.database.all(
            """SELECT e.started_at, COALESCE(e.corrected_zone_type, z.type) AS zone_type,
                      (SELECT r.decision FROM human_reviews r WHERE r.event_id = e.id
                       ORDER BY r.created_at DESC LIMIT 1) AS decision
               FROM events e JOIN zones z ON z.id = e.zone_id
               WHERE e.started_at >= ? AND e.started_at < ?
               AND (e.pet_id = ? OR EXISTS (SELECT 1 FROM event_pets ep WHERE ep.event_id = e.id AND ep.pet_id = ?))""",
            (start, end, pet_id, pet_id),
        )
