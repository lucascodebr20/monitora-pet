from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.controllers.schemas.pet_schema import PetCreateRequest
from app.core.container import Container, get_container


router = APIRouter(prefix="/api/pets", tags=["pets"])


@router.get("")
def list_pets(container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"pets": container.pet_service.list()}


@router.post("", status_code=201)
def create_pet(request: PetCreateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_service.create(request.name, request.species, request.description, request.photo_data)


@router.put("/{pet_id}")
def update_pet(pet_id: str, request: PetCreateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_service.update(pet_id, request.name, request.species, request.description, request.photo_data)


@router.delete("/{pet_id}", status_code=204)
def delete_pet(pet_id: str, container: Container = Depends(get_container)) -> None:
    container.pet_service.delete(pet_id)


@router.get("/{pet_id}/photo")
def pet_photo(pet_id: str, container: Container = Depends(get_container)) -> FileResponse:
    return FileResponse(container.pet_service.photo(pet_id), media_type="image/jpeg")


@router.get("/{pet_id}/references")
def list_pet_references(pet_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"images": container.pet_service.reference_images(pet_id)}


@router.get("/{pet_id}/references/{image_id}")
def pet_reference(pet_id: str, image_id: str, container: Container = Depends(get_container)) -> FileResponse:
    return FileResponse(container.pet_service.reference_image(pet_id, image_id), media_type="image/jpeg")


@router.delete("/{pet_id}/references/{image_id}", status_code=204)
def delete_pet_reference(pet_id: str, image_id: str, container: Container = Depends(get_container)) -> None:
    container.pet_service.delete_reference_image(pet_id, image_id)
