from __future__ import annotations

from typing import Any

from app.domain.enums import PetSpecies
from app.infra.ai.identification_calibration import (
    CALIBRATION_INTERVAL,
    METHOD,
    MINIMUM_MARGIN,
    MINIMUM_SIMILARITY,
    IdentificationCalibrator,
)
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository


class IdentificationService:
    def __init__(self, repository: PetIdentificationRepository | None, calibrator: IdentificationCalibrator) -> None:
        self.repository = repository
        self.calibrator = calibrator

    def logs(self, page: int, page_size: int) -> dict[str, Any]:
        if self.repository is None:
            return {
                "analyses": [], "total": 0, "page": page, "page_size": page_size,
                "calibrations": {species.value: self._default_calibration() for species in PetSpecies},
                "metrics": {}, "method": METHOD,
            }
        return {
            "analyses": self.repository.list_analyses(page_size, (page - 1) * page_size),
            "total": self.repository.count_analyses(),
            "page": page,
            "page_size": page_size,
            "calibrations": {species.value: self._calibration(species.value) for species in PetSpecies},
            "metrics": self.repository.performance_metrics(METHOD),
            "method": METHOD,
        }

    def _calibration(self, species: str) -> dict[str, Any]:
        return {
            **self.repository.current_calibration(METHOD, species),
            "interactions_until_calibration": self.calibrator.interactions_until_next(species),
        }

    @staticmethod
    def _default_calibration() -> dict[str, Any]:
        return {
            "minimum_similarity": MINIMUM_SIMILARITY,
            "minimum_margin": MINIMUM_MARGIN,
            "interaction_count": 0,
            "accuracy": None,
            "created_at": None,
            "interactions_until_calibration": CALIBRATION_INTERVAL,
        }
