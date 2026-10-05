from typing import Any

from fastapi import APIRouter, Depends

from app.controllers.schemas.zone_schema import ZoneCreateRequest
from app.core.container import Container, get_container


router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("")
def list_zones(camera_id: str | None = None, container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"zones": container.zone_service.list(camera_id)}


@router.post("", status_code=201)
def create_zone(request: ZoneCreateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.zone_service.create(request.to_command())


@router.put("/{zone_id}")
def update_zone(zone_id: str, request: ZoneCreateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.zone_service.update(zone_id, request.to_command())


@router.delete("/{zone_id}", status_code=204)
def delete_zone(zone_id: str, container: Container = Depends(get_container)) -> None:
    container.zone_service.delete(zone_id)
