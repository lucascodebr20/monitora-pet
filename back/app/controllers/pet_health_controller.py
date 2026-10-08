from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from app.controllers.schemas.pet_health_schema import (
    DoseRequest,
    ExamRequest,
    FoodPeriodRequest,
    TreatmentEntryRequest,
    TreatmentRequest,
    WeightRequest,
)
from app.core.container import Container, get_container
from app.domain.errors import InvalidDomainValueError
from app.infra.media.health_file_store import MAX_FILE_BYTES

router = APIRouter(prefix="/api/pets/{pet_id}/health", tags=["pet-health"])
reminders_router = APIRouter(prefix="/api/health-reminders", tags=["pet-health"])


async def read_upload(request: Request) -> bytes:
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_FILE_BYTES:
            raise InvalidDomainValueError("O arquivo deve ter até 25 MB.")
    return bytes(content)


@reminders_router.get("")
def list_reminders(container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"reminders": container.pet_health_service.reminders()}


@router.get("/summary")
def summary(pet_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.summary(pet_id)


@router.get("/timeline")
def timeline(pet_id: str, start: str | None = None, end: str | None = None,
             container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.timeline(pet_id, start, end)


@router.get("/food")
def list_food(pet_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"items": container.pet_health_service.list("food", pet_id)}


@router.post("/food", status_code=201)
def create_food(pet_id: str, request: FoodPeriodRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    values = request.model_dump(exclude={"replace_current"})
    return container.pet_health_service.create_food(pet_id, values, request.replace_current)


@router.put("/food/{record_id}")
def update_food(pet_id: str, record_id: str, request: FoodPeriodRequest,
                container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.update_food(pet_id, record_id, request.model_dump(exclude={"replace_current"}))


@router.get("/weights")
def list_weights(pet_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"items": container.pet_health_service.list("weight", pet_id)}


@router.post("/weights", status_code=201)
def create_weight(pet_id: str, request: WeightRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.create_weight(pet_id, request.model_dump())


@router.get("/exams")
def list_exams(pet_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"items": container.pet_health_service.list("exam", pet_id)}


@router.post("/exams", status_code=201)
def create_exam(pet_id: str, request: ExamRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.create_exam(pet_id, request.model_dump())


@router.put("/exams/{record_id}")
def update_exam(pet_id: str, record_id: str, request: ExamRequest,
                container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.update_exam(pet_id, record_id, request.model_dump())


@router.post("/exams/{exam_id}/attachments", status_code=201)
async def upload_exam_file(pet_id: str, exam_id: str, request: Request, filename: str = "arquivo",
                           container: Container = Depends(get_container)) -> dict[str, Any]:
    content = await read_upload(request)
    return container.pet_health_service.add_attachment(pet_id, content, filename, exam_id=exam_id)


@router.get("/treatments")
def list_treatments(pet_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"items": container.pet_health_service.list("treatment", pet_id)}


@router.post("/treatments", status_code=201)
def create_treatment(pet_id: str, request: TreatmentRequest,
                     container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.create_treatment(pet_id, request.model_dump())


@router.put("/treatments/{record_id}")
def update_treatment(pet_id: str, record_id: str, request: TreatmentRequest,
                     container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.update_treatment(pet_id, record_id, request.model_dump())


@router.post("/treatments/{treatment_id}/entries", status_code=201)
def create_entry(pet_id: str, treatment_id: str, request: TreatmentEntryRequest,
                 container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.create_entry(pet_id, treatment_id, request.model_dump())


@router.delete("/treatments/{treatment_id}/entries/{entry_id}", status_code=204)
def delete_entry(pet_id: str, treatment_id: str, entry_id: str, container: Container = Depends(get_container)) -> None:
    container.pet_health_service.delete_entry(pet_id, treatment_id, entry_id)


@router.post("/treatments/{treatment_id}/entries/{entry_id}/attachments", status_code=201)
async def upload_entry_photo(pet_id: str, treatment_id: str, entry_id: str, request: Request,
                             filename: str = "foto", container: Container = Depends(get_container)) -> dict[str, Any]:
    content = await read_upload(request)
    return container.pet_health_service.add_attachment(
        pet_id, content, filename, treatment_id=treatment_id, entry_id=entry_id
    )


@router.get("/doses")
def list_doses(pet_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"items": container.pet_health_service.list("dose", pet_id)}


@router.post("/doses", status_code=201)
def create_dose(pet_id: str, request: DoseRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.create_dose(pet_id, request.model_dump())


@router.put("/doses/{record_id}")
def update_dose(pet_id: str, record_id: str, request: DoseRequest,
                container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.pet_health_service.update_dose(pet_id, record_id, request.model_dump())


@router.get("/attachments/{attachment_id}")
def attachment(pet_id: str, attachment_id: str, thumbnail: bool = False,
               container: Container = Depends(get_container)) -> FileResponse:
    path, media_type, name = container.pet_health_service.attachment_file(pet_id, attachment_id, thumbnail)
    return FileResponse(path, media_type=media_type,
                        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}",
                                 "X-Content-Type-Options": "nosniff"})


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(pet_id: str, attachment_id: str, container: Container = Depends(get_container)) -> None:
    container.pet_health_service.delete_attachment(pet_id, attachment_id)


@router.delete("/{kind}/{record_id}", status_code=204)
def delete_record(pet_id: str, kind: str, record_id: str, container: Container = Depends(get_container)) -> None:
    kinds = {"food": "food", "weights": "weight", "exams": "exam", "treatments": "treatment", "doses": "dose"}
    if kind not in kinds:
        raise InvalidDomainValueError("Tipo de registro desconhecido.")
    container.pet_health_service.delete(kinds[kind], pet_id, record_id)
