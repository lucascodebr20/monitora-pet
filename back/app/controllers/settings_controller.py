from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from app.core.container import Container, get_container
from app.domain.enums import HouseholdSpecies

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    retention_days: int | None = Field(default=None, ge=1, le=365)
    household_species: HouseholdSpecies | None = None

    @model_validator(mode="after")
    def require_a_field(self) -> "SettingsUpdateRequest":
        if self.retention_days is None and self.household_species is None:
            raise ValueError("Informe ao menos uma configuração para salvar.")
        return self


def _view(container: Container) -> dict[str, Any]:
    return {**container.retention_service.view(), **container.household_service.view()}


@router.get("")
def get_settings(container: Container = Depends(get_container)) -> dict[str, Any]:
    return _view(container)


@router.put("")
def update_settings(request: SettingsUpdateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    if request.retention_days is not None:
        container.retention_service.set_retention_days(request.retention_days)
    if request.household_species is not None:
        container.household_service.set_species(request.household_species)
    return _view(container)
