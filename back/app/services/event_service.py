from __future__ import annotations

from dataclasses import asdict
from typing import Any
from pathlib import Path
from uuid import uuid4

from app.domain.errors import EntityNotFoundError
from app.domain.errors import InvalidDomainValueError
from app.domain.enums import ReviewDecision, ZoneType
from app.infra.database.database import utc_now
from app.infra.media.clip_store import ClipStore
from app.infra.media.pet_image_store import PetImageStore
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.pet_repository import PetRepository
from app.infra.media.snapshot_store import SnapshotStore
from app.services.commands import ReviewEventCommand


class EventService:
    def __init__(self, repository: EventRepository, snapshot_store: SnapshotStore, clip_store: ClipStore,
                 pet_repository: PetRepository, pet_image_store: PetImageStore) -> None:
        self.repository = repository
        self.snapshot_store = snapshot_store
        self.clip_store = clip_store
        self.pet_repository = pet_repository
        self.pet_image_store = pet_image_store

    def list(
        self,
        camera_id: str | None = None,
        zone_id: str | None = None,
        date: str | None = None,
        pending_review: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.repository.list(camera_id, zone_id, date, pending_review, limit)

    def search(
        self,
        page: int,
        page_size: int,
        pet_id: str | None = None,
        zone_type: ZoneType | None = None,
        pending_review: bool = False,
        camera_id: str | None = None,
        zone_id: str | None = None,
        date: str | None = None,
    ) -> dict[str, Any]:
        events, total = self.repository.search(
            page, page_size, pet_id, zone_type.value if zone_type else None, pending_review,
            camera_id, zone_id, date,
        )
        return {"events": events, "total": total, "page": page, "page_size": page_size}

    def review(self, event_id: str, request: ReviewEventCommand) -> dict[str, Any]:
        if not self.repository.exists(event_id):
            raise EntityNotFoundError("Evento não encontrado.")
        if self.repository.has_review(event_id):
            raise InvalidDomainValueError("Este registro já foi revisado.")
        event = self.repository.get(event_id)
        if request.decision == ReviewDecision.CORRECTED:
            if request.zone_type not in {ZoneType.WATER, ZoneType.FOOD, ZoneType.LITTER}:
                raise InvalidDomainValueError("Selecione água, comida ou caixa de areia como tipo corrigido.")
            if request.zone_type.value == event["zone_type"]:
                raise InvalidDomainValueError("O tipo corrigido deve ser diferente do tipo detectado.")
        elif request.zone_type is not None:
            raise InvalidDomainValueError("O tipo da área só pode ser informado ao corrigir o registro.")
        if request.decision == ReviewDecision.FALSE_POSITIVE and request.pet_id:
            raise InvalidDomainValueError("Uma evidência recusada não pode ser atribuída a um pet.")
        pet = self.pet_repository.get(request.pet_id) if request.pet_id else None
        if request.pet_id and not pet:
            raise EntityNotFoundError("Pet não encontrado.")
        if pet and pet["species"] != event["detected_species"]:
            raise InvalidDomainValueError("A espécie do pet não corresponde ao animal detectado.")
        confirmed_pet = pet if request.decision.value in {"CONFIRMED", "CORRECTED"} else None
        review = {
            "id": str(uuid4()),
            "event_id": event_id,
            **asdict(request),
            "pet_id": confirmed_pet["id"] if confirmed_pet else None,
            "created_at": utc_now(),
        }
        self.repository.complete_review(review)
        return review

    def snapshot(self, event_id: str) -> Path:
        event = self.repository.get(event_id)
        if not event:
            raise EntityNotFoundError("Evento não encontrado.")
        if not event.get("snapshot_path"):
            raise EntityNotFoundError("Este evento não possui snapshot.")
        path = self.snapshot_store.resolve(event["snapshot_path"])
        if not path.is_file():
            raise EntityNotFoundError("O snapshot deste evento não está mais disponível.")
        return path

    def clip(self, event_id: str) -> Path:
        event = self.repository.get(event_id)
        if not event:
            raise EntityNotFoundError("Evento não encontrado.")
        if not event.get("clip_path"):
            raise EntityNotFoundError("Este evento ainda não possui vídeo.")
        path = self.clip_store.resolve(event["clip_path"])
        if not path.is_file():
            raise EntityNotFoundError("O vídeo deste evento não está mais disponível.")
        return path
