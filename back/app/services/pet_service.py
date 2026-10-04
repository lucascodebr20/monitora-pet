from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.enums import PetSpecies
from app.domain.errors import EntityNotFoundError, InvalidDomainValueError
from app.infra.media.pet_image_store import PetImageStore
from app.infra.repositories.pet_repository import PetRepository


class PetService:
    def __init__(self, repository: PetRepository, image_store: PetImageStore) -> None:
        self.repository = repository
        self.image_store = image_store

    def list(self) -> list[dict[str, Any]]:
        return self.repository.list()

    def get(self, pet_id: str) -> dict[str, Any]:
        pet = self.repository.get(pet_id)
        if not pet:
            raise EntityNotFoundError("Pet não encontrado.")
        return pet

    def create(self, name: str, species: PetSpecies, description: str, photo_data: str | None) -> dict[str, Any]:
        if not photo_data:
            raise InvalidDomainValueError("Adicione uma foto para cadastrar o pet.")
        photo_path = self._save_photo(photo_data)
        return self.repository.create(name.strip(), species.value, description.strip(), photo_path)

    def update(self, pet_id: str, name: str, species: PetSpecies, description: str, photo_data: str | None) -> dict[str, Any]:
        current = self.get(pet_id)
        if current["species"] != species.value and self.repository.has_history(pet_id):
            raise InvalidDomainValueError("A espécie não pode mudar depois que o pet tiver eventos ou capturas.")
        photo_path = self._save_photo(photo_data)
        return self.repository.update(pet_id, name.strip(), species.value, description.strip(), photo_path)

    def delete(self, pet_id: str) -> None:
        self.get(pet_id)
        self.repository.delete(pet_id)

    def _save_photo(self, photo_data: str | None) -> str | None:
        if not photo_data:
            return None
        try:
            return self.image_store.save_data_url(photo_data)
        except ValueError as error:
            raise InvalidDomainValueError(str(error)) from error

    def photo(self, pet_id: str) -> Path:
        pet = self.get(pet_id)
        if not pet.get("photo_path"):
            raise EntityNotFoundError("Este pet ainda não possui foto.")
        path = self.image_store.resolve(pet["photo_path"])
        if not path.is_file():
            raise EntityNotFoundError("A foto deste pet não está mais disponível.")
        return path

    def reference_images(self, pet_id: str) -> list[dict[str, Any]]:
        self.get(pet_id)
        images = self.repository.list_reference_images(pet_id)
        for image in images:
            image["url"] = f"/api/pets/{pet_id}/references/{image['id']}"
        return images

    def reference_image(self, pet_id: str, image_id: str) -> Path:
        self.get(pet_id)
        image = self.repository.get_reference_image(pet_id, image_id)
        if not image:
            raise EntityNotFoundError("Imagem de referência não encontrada.")
        path = self.image_store.resolve(image["image_path"])
        if not path.is_file():
            raise EntityNotFoundError("A imagem de referência não está mais disponível.")
        return path

    def delete_reference_image(self, pet_id: str, image_id: str) -> None:
        self.get(pet_id)
        if not self.repository.delete_reference_image(pet_id, image_id):
            raise EntityNotFoundError("Imagem de referência não encontrada.")
