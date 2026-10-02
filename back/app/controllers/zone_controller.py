from typing import Any

from fastapi import APIRouter

from app.controllers.schemas.zone_schema import ZoneCreateRequest
from app.core.container import zone_service


router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("")
def list_zones(camera_id: str | None = None) -> dict[str, Any]:
    return {"zones": zone_service.list(camera_id)}


@router.post("", status_code=201)
def create_zone(request: ZoneCreateRequest) -> dict[str, Any]:
    return zone_service.create(request.to_command())


@router.delete("/{zone_id}", status_code=204)
def delete_zone(zone_id: str) -> None:
    zone_service.delete(zone_id)
