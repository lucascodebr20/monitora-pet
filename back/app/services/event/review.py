from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from app.domain.clock import utc_now
from app.domain.enums import ReviewDecision, ZoneType
from app.domain.errors import EntityNotFoundError, InvalidDomainValueError
from app.infra.ai.identification_calibration import IdentificationCalibrator
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.pet_repository import PetRepository
from app.services.event.commands import ReviewEventCommand

CORRECTABLE_ZONE_TYPES = {ZoneType.WATER, ZoneType.FOOD, ZoneType.LITTER}


class EventReviewService:
    def __init__(
        self,
        repository: EventRepository,
        pet_repository: PetRepository,
        calibrator: IdentificationCalibrator | None = None,
    ) -> None:
        self.repository = repository
        self.pet_repository = pet_repository
        self.calibrator = calibrator

    def review(self, event_id: str, request: ReviewEventCommand) -> dict[str, Any]:
        if not self.repository.exists(event_id):
            raise EntityNotFoundError("Evento não encontrado.")
        if self.repository.has_review(event_id):
            raise InvalidDomainValueError("Este registro já foi revisado.")
        event = self.repository.get(event_id)
        self._validate(request, event)
        pet = self.pet_repository.get(request.pet_id) if request.pet_id else None
        if request.pet_id and not pet:
            raise EntityNotFoundError("Pet não encontrado.")
        confirmed_pet = pet if request.decision in {ReviewDecision.CONFIRMED, ReviewDecision.CORRECTED} else None
        corrected_zone_type = (
            request.zone_type.value if request.decision == ReviewDecision.CORRECTED and request.zone_type else None
        )
        review = {
            "id": str(uuid4()),
            "event_id": event_id,
            **asdict(request),
            "pet_id": confirmed_pet["id"] if confirmed_pet else None,
            "created_at": utc_now(),
        }
        self.repository.complete_review(review, review["pet_id"], corrected_zone_type)
        if confirmed_pet and self.calibrator:
            self.calibrator.learn_from_review(event_id, confirmed_pet["id"])
        return review

    @staticmethod
    def _validate(request: ReviewEventCommand, event: dict[str, Any]) -> None:
        if request.decision == ReviewDecision.CORRECTED:
            if request.zone_type not in CORRECTABLE_ZONE_TYPES:
                raise InvalidDomainValueError("Selecione água, comida ou caixa de areia como tipo corrigido.")
            if request.zone_type.value == event["zone_type"]:
                raise InvalidDomainValueError("O tipo corrigido deve ser diferente do tipo detectado.")
        elif request.zone_type is not None:
            raise InvalidDomainValueError("O tipo da área só pode ser informado ao corrigir o registro.")
        if request.decision == ReviewDecision.FALSE_POSITIVE and request.pet_id:
            raise InvalidDomainValueError("Uma evidência recusada não pode ser atribuída a um pet.")
