from typing import Any

from fastapi import APIRouter, Depends

from app.core.container import Container, get_container


router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/{camera_id}")
def camera_feedback(camera_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    container.camera_service.get(camera_id)
    return container.monitoring_service.feedback(camera_id)
