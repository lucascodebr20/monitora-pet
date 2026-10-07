from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.container import Container, get_container
from app.services.event.auto_review import MAX_TARGET_PRECISION, MIN_TARGET_PRECISION

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    retention_days: int = Field(ge=1, le=365)
    auto_review_enabled: bool | None = None
    auto_review_target_precision: float | None = Field(
        default=None, ge=MIN_TARGET_PRECISION, le=MAX_TARGET_PRECISION
    )


def _view(container: Container) -> dict[str, Any]:
    return {**container.retention_service.view(), **container.auto_review_service.view()}


@router.get("")
def get_settings(container: Container = Depends(get_container)) -> dict[str, Any]:
    return _view(container)


@router.put("")
def update_settings(request: SettingsUpdateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    container.retention_service.set_retention_days(request.retention_days)
    container.auto_review_service.update(request.auto_review_enabled, request.auto_review_target_precision)
    return _view(container)
