from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.container import Container, get_container

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    retention_days: int = Field(ge=1, le=365)


@router.get("")
def get_settings(container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.retention_service.view()


@router.put("")
def update_settings(request: SettingsUpdateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    container.retention_service.set_retention_days(request.retention_days)
    return container.retention_service.view()
