from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.controllers.schemas.pet_schema import PetCreateRequest
from app.core.container import pet_service


router = APIRouter(prefix="/api/pets", tags=["pets"])


@router.get("")
def list_pets() -> dict[str, Any]:
    return {"pets": pet_service.list()}


@router.post("", status_code=201)
def create_pet(request: PetCreateRequest) -> dict[str, Any]:
    return pet_service.create(request.name, request.species, request.description, request.photo_data)


@router.put("/{pet_id}")
def update_pet(pet_id: str, request: PetCreateRequest) -> dict[str, Any]:
    return pet_service.update(pet_id, request.name, request.species, request.description, request.photo_data)


@router.delete("/{pet_id}", status_code=204)
def delete_pet(pet_id: str) -> None:
    pet_service.delete(pet_id)


@router.get("/{pet_id}/photo")
def pet_photo(pet_id: str) -> FileResponse:
    return FileResponse(pet_service.photo(pet_id), media_type="image/jpeg")


@router.get("/{pet_id}/references")
def list_pet_references(pet_id: str) -> dict[str, Any]:
    return {"images": pet_service.reference_images(pet_id)}


@router.get("/{pet_id}/references/{image_id}")
def pet_reference(pet_id: str, image_id: str) -> FileResponse:
    return FileResponse(pet_service.reference_image(pet_id, image_id), media_type="image/jpeg")
