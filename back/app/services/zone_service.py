from __future__ import annotations

from typing import Any

from app.domain.errors import EntityNotFoundError
from app.domain.geometry import validate_polygon
from app.infra.repositories.zone_repository import ZoneRepository
from app.services.commands import CreateZoneCommand
from app.services.camera_service import CameraService


class ZoneService:
    def __init__(self, repository: ZoneRepository, camera_service: CameraService) -> None:
        self.repository = repository
        self.camera_service = camera_service

    def list(self, camera_id: str | None = None) -> list[dict[str, Any]]:
        return self.repository.list(camera_id)

    def create(self, request: CreateZoneCommand) -> dict[str, Any]:
        self.camera_service.get(request.camera_id)
        validate_polygon(list(request.polygon))
        return self.repository.create({
            "camera_id": request.camera_id,
            "name": request.name,
            "type": request.type,
            "polygon": request.polygon,
            "minimum_presence_seconds": request.minimum_presence_seconds,
            "absence_tolerance_seconds": request.absence_tolerance_seconds,
            "cooldown_seconds": request.cooldown_seconds,
        })

    def delete(self, zone_id: str) -> None:
        if not self.repository.get(zone_id):
            raise EntityNotFoundError("Zona não encontrada.")
        self.repository.delete(zone_id)

    def update(self, zone_id: str, request: CreateZoneCommand) -> dict[str, Any]:
        zone = self.repository.get(zone_id)
        if not zone:
            raise EntityNotFoundError("Zona não encontrada.")
        if zone["camera_id"] != request.camera_id:
            raise EntityNotFoundError("A zona não pertence à câmera informada.")
        validate_polygon(list(request.polygon))
        return self.repository.update(zone_id, {
            "name": request.name,
            "type": request.type,
            "polygon": request.polygon,
            "minimum_presence_seconds": request.minimum_presence_seconds,
            "absence_tolerance_seconds": request.absence_tolerance_seconds,
            "cooldown_seconds": request.cooldown_seconds,
        })
