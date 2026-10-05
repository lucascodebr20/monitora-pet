from typing import Any

from app.infra.ai.pet_identifier import PetIdentifier


class IdentificationService:
    """Expõe o histórico e a calibração da identificação automática de pets."""

    def __init__(self, identifier: PetIdentifier | None) -> None:
        self.identifier = identifier

    def logs(self, page: int, page_size: int) -> dict[str, Any]:
        if self.identifier is None:
            return {"analyses": [], "total": 0, "page": page, "page_size": page_size,
                    "calibration": None, "interactions_until_calibration": 0, "metrics": {}}
        return self.identifier.logs(page, page_size)
