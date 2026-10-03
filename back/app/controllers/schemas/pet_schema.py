from pydantic import BaseModel, Field

from app.domain.enums import PetSpecies


class PetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    species: PetSpecies
    description: str = Field(default="", max_length=500)
    photo_data: str | None = Field(default=None, max_length=11_000_000)
