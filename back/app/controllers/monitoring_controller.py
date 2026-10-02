from typing import Any

from fastapi import APIRouter

from app.core.container import camera_service, monitoring_service


router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/{camera_id}")
def camera_feedback(camera_id: str) -> dict[str, Any]:
    camera_service.get(camera_id)
    return monitoring_service.feedback(camera_id)
