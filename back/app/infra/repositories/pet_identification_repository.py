from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.infra.database.database import Database, utc_now


class PetIdentificationRepository:
    DEFAULT_MINIMUM_SIMILARITY = 0.72
    DEFAULT_MINIMUM_MARGIN = 0.08

    def __init__(self, database: Database) -> None:
        self.database = database

    def current_calibration(self) -> dict[str, Any]:
        calibration = self.database.one(
            "SELECT * FROM pet_identification_calibrations ORDER BY id DESC LIMIT 1"
        )
        return calibration or {
            "id": 0,
            "minimum_similarity": self.DEFAULT_MINIMUM_SIMILARITY,
            "minimum_margin": self.DEFAULT_MINIMUM_MARGIN,
            "interaction_count": 0,
            "accuracy": None,
            "created_at": None,
        }

    def create_analysis(
        self,
        event_id: str,
        species: str,
        capture_path: str | None,
        decision: str,
        selected_pet_id: str | None,
        selected_confidence: float | None,
        minimum_similarity: float,
        minimum_margin: float,
        scores: list[dict[str, Any]],
    ) -> None:
        analysis_id = str(uuid4())
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO pet_identification_analyses
                   (id, event_id, species, capture_path, decision, selected_pet_id,
                    selected_confidence, minimum_similarity, minimum_margin, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    analysis_id, event_id, species, capture_path, decision, selected_pet_id,
                    selected_confidence, minimum_similarity, minimum_margin, utc_now(),
                ),
            )
            connection.executemany(
                """INSERT INTO pet_identification_scores
                   (analysis_id, pet_id, confidence, reference_count, rank)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (analysis_id, score["pet_id"], score["confidence"], score["reference_count"], rank)
                    for rank, score in enumerate(scores, start=1)
                ],
            )

    def mark_review(self, event_id: str, pet_id: str) -> bool:
        analysis = self.database.one(
            "SELECT selected_pet_id FROM pet_identification_analyses WHERE event_id = ?",
            (event_id,),
        )
        if not analysis:
            return False
        self.database.execute(
            """UPDATE pet_identification_analyses
               SET reviewed_pet_id = ?, reviewed_at = ?, was_correct = ?
               WHERE event_id = ?""",
            (pet_id, utc_now(), int(analysis["selected_pet_id"] == pet_id), event_id),
        )
        return True

    def reviewed_count(self) -> int:
        row = self.database.one(
            "SELECT COUNT(*) AS total FROM pet_identification_analyses WHERE reviewed_pet_id IS NOT NULL"
        )
        return int(row["total"]) if row else 0

    def reviewed_samples(self) -> list[dict[str, Any]]:
        analyses = self.database.all(
            """SELECT id, selected_pet_id, reviewed_pet_id
               FROM pet_identification_analyses
               WHERE reviewed_pet_id IS NOT NULL ORDER BY reviewed_at"""
        )
        for analysis in analyses:
            analysis["scores"] = self.database.all(
                "SELECT pet_id, confidence FROM pet_identification_scores WHERE analysis_id = ?",
                (analysis["id"],),
            )
        return analyses

    def create_calibration(
        self,
        minimum_similarity: float,
        minimum_margin: float,
        interaction_count: int,
        accuracy: float,
    ) -> None:
        self.database.execute(
            """INSERT INTO pet_identification_calibrations
               (minimum_similarity, minimum_margin, interaction_count, accuracy, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (minimum_similarity, minimum_margin, interaction_count, accuracy, utc_now()),
        )

    def list_analyses(self, limit: int = 100) -> list[dict[str, Any]]:
        analyses = self.database.all(
            """SELECT a.*, selected.name AS selected_pet_name, reviewed.name AS reviewed_pet_name,
                      c.name AS camera_name, z.name AS zone_name
               FROM pet_identification_analyses a
               JOIN events e ON e.id = a.event_id
               JOIN cameras c ON c.id = e.camera_id
               JOIN zones z ON z.id = e.zone_id
               LEFT JOIN pets selected ON selected.id = a.selected_pet_id
               LEFT JOIN pets reviewed ON reviewed.id = a.reviewed_pet_id
               ORDER BY a.created_at DESC LIMIT ?""",
            (limit,),
        )
        for analysis in analyses:
            analysis["scores"] = self.database.all(
                """SELECT s.pet_id, p.name AS pet_name, s.confidence, s.reference_count, s.rank
                   FROM pet_identification_scores s JOIN pets p ON p.id = s.pet_id
                   WHERE s.analysis_id = ? ORDER BY s.rank""",
                (analysis["id"],),
            )
        return analyses
