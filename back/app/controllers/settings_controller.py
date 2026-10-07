from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from app.core.container import Container, get_container
from app.domain.enums import HouseholdSpecies
from app.services.event.auto_review import MAX_TARGET_PRECISION, MIN_TARGET_PRECISION

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    retention_days: int | None = Field(default=None, ge=1, le=365)
    retention_enabled: bool | None = None
    household_species: HouseholdSpecies | None = None
    auto_review_enabled: bool | None = None
    auto_review_target_precision: float | None = Field(
        default=None, ge=MIN_TARGET_PRECISION, le=MAX_TARGET_PRECISION
    )

    @model_validator(mode="after")
    def require_a_field(self) -> "SettingsUpdateRequest":
        if all(
            value is None
            for value in (
                self.retention_days,
                self.retention_enabled,
                self.household_species,
                self.auto_review_enabled,
                self.auto_review_target_precision,
            )
        ):
            raise ValueError("Informe ao menos uma configuração para salvar.")
        return self


def _view(container: Container) -> dict[str, Any]:
    return {
        **container.retention_service.view(),
        **container.household_service.view(),
        **container.auto_review_service.view(),
    }


@router.get("")
def get_settings(container: Container = Depends(get_container)) -> dict[str, Any]:
    return _view(container)


@router.put("")
def update_settings(request: SettingsUpdateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    if request.retention_days is not None:
        container.retention_service.set_retention_days(request.retention_days)
    if request.retention_enabled is not None:
        container.retention_service.set_enabled(request.retention_enabled)
    if request.household_species is not None:
        container.household_service.set_species(request.household_species)
    container.auto_review_service.update(request.auto_review_enabled, request.auto_review_target_precision)
    return _view(container)
