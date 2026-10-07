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

# Desfechos em que o humano afirmou qual gato era: so estes treinam o
# identificador. NO_ACTION entra porque o gato estava certo — o que nao
# aconteceu foi a acao, que e outra pergunta.
IDENTIFYING_DECISIONS = {ReviewDecision.CONFIRMED, ReviewDecision.CORRECTED, ReviewDecision.NO_ACTION}


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
        self._validate_pets(request)
        pet = self.pet_repository.get(request.pet_id) if request.pet_id else None
        if request.pet_id and not pet:
            raise EntityNotFoundError("Pet não encontrado.")
        confirmed_pet = pet if request.decision in IDENTIFYING_DECISIONS else None
        corrected_zone_type = (
            request.zone_type.value if request.decision == ReviewDecision.CORRECTED and request.zone_type else None
        )
        review = {
            "id": str(uuid4()),
            "event_id": event_id,
            **{key: value for key, value in asdict(request).items() if key != "pet_ids"},
            "pet_id": confirmed_pet["id"] if confirmed_pet else None,
            "created_at": utc_now(),
        }
        if request.decision == ReviewDecision.MULTIPLE_PETS:
            # A visita vale, mas nenhuma atribuicao unica faria sentido: o evento
            # fica sem pet_id e os gatos presentes vao para event_pets. Tambem nao
            # vira referencia, porque a captura tem mais de um animal.
            self.repository.complete_multiple_pets_review(review, list(request.pet_ids))
        else:
            self.repository.complete_review(review, review["pet_id"], corrected_zone_type)
        if confirmed_pet and self.calibrator:
            self.calibrator.learn_from_review(event_id, confirmed_pet["id"])
        return review

    def _validate_pets(self, request: ReviewEventCommand) -> None:
        if request.decision != ReviewDecision.MULTIPLE_PETS:
            if request.pet_ids:
                raise InvalidDomainValueError("Vários gatos só podem ser informados ao marcar mais de um animal.")
            return
        unique = dict.fromkeys(request.pet_ids)
        if len(unique) < 2:
            raise InvalidDomainValueError("Selecione pelo menos dois gatos.")
        for pet_id in unique:
            if not self.pet_repository.get(pet_id):
                raise EntityNotFoundError("Pet não encontrado.")

    @staticmethod
    def _validate(request: ReviewEventCommand, event: dict[str, Any]) -> None:
        if request.decision == ReviewDecision.NO_ACTION and not request.pet_id:
            raise InvalidDomainValueError("Informe qual gato esteve na área.")
        if request.decision == ReviewDecision.MULTIPLE_PETS and request.pet_id:
            raise InvalidDomainValueError("Com mais de um gato, use a lista de animais.")
        if request.decision == ReviewDecision.CORRECTED:
            if request.zone_type not in CORRECTABLE_ZONE_TYPES:
                raise InvalidDomainValueError("Selecione água, comida ou caixa de areia como tipo corrigido.")
            if request.zone_type.value == event["zone_type"]:
                raise InvalidDomainValueError("O tipo corrigido deve ser diferente do tipo detectado.")
        elif request.zone_type is not None:
            raise InvalidDomainValueError("O tipo da área só pode ser informado ao corrigir o registro.")
        if request.decision == ReviewDecision.FALSE_POSITIVE and request.pet_id:
            raise InvalidDomainValueError("Uma evidência recusada não pode ser atribuída a um pet.")
