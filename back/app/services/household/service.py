from __future__ import annotations

from app.domain.enums import HouseholdSpecies
from app.infra.repositories.settings_repository import SettingsRepository

HOUSEHOLD_SPECIES_KEY = "household_species"


class HouseholdService:
    def __init__(self, settings: SettingsRepository) -> None:
        self.settings = settings

    def species(self) -> HouseholdSpecies | None:
        value = self.settings.get(HOUSEHOLD_SPECIES_KEY)
        try:
            return HouseholdSpecies(value) if value else None
        except ValueError:
            return None

    def set_species(self, species: HouseholdSpecies) -> HouseholdSpecies:
        self.settings.set(HOUSEHOLD_SPECIES_KEY, species.value)
        return species

    def view(self) -> dict[str, str | None]:
        species = self.species()
        return {"household_species": species.value if species else None}
