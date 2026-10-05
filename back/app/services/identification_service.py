from __future__ import annotations

from typing import Any

from app.infra.ai.identification_calibration import CALIBRATION_INTERVAL, METHOD, IdentificationCalibrator
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository


class IdentificationService:
    def __init__(self, repository: PetIdentificationRepository | None, calibrator: IdentificationCalibrator) -> None:
        self.repository = repository
        self.calibrator = calibrator

    def logs(self, page: int, page_size: int) -> dict[str, Any]:
        if self.repository is None:
            return {
                "analyses": [], "total": 0, "page": page, "page_size": page_size, "calibration": None,
                "interactions_until_calibration": CALIBRATION_INTERVAL, "metrics": {}, "method": METHOD,
            }
        return {
            "analyses": self.repository.list_analyses(page_size, (page - 1) * page_size),
            "total": self.repository.count_analyses(),
            "page": page,
            "page_size": page_size,
            "calibration": self.repository.current_calibration(METHOD),
            "interactions_until_calibration": self.calibrator.interactions_until_next(),
            "metrics": self.repository.performance_metrics(METHOD),
            "method": METHOD,
        }
