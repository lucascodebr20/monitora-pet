from typing import Any

from fastapi import APIRouter, Depends

from app.core.container import Container, get_container

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def job_state(container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.import_worker.state()


@router.post("/import", status_code=202)
def start_import(camera_id: str | None = None, container: Container = Depends(get_container)) -> dict[str, Any]:
    if camera_id:
        container.camera_service.get(camera_id)
    return container.import_worker.request_import(camera_id)


@router.post("/sync/{camera_id}", status_code=202)
def start_sync(camera_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    container.camera_service.get(camera_id)
    return container.import_worker.request_sync(camera_id)


@router.post("/cancel")
def cancel_jobs(container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.import_worker.cancel()
