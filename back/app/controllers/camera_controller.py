from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.controllers.schemas.camera_schema import CameraCreateRequest, CameraCredentialsRequest
from app.core.container import camera_discovery_service, camera_service


router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("/discover")
def discover_cameras(fallback: bool = False) -> dict[str, object]:
    return {"cameras": camera_discovery_service.discover(fallback)}


@router.get("")
def list_cameras() -> dict[str, Any]:
    return {"cameras": camera_service.list()}


@router.post("", status_code=201)
def create_camera(request: CameraCreateRequest) -> dict[str, Any]:
    return camera_service.create(request.to_command())


@router.post("/{camera_id}/connect")
def connect_camera(camera_id: str, credentials: CameraCredentialsRequest) -> dict[str, Any]:
    return camera_service.connect(camera_id, credentials.to_command())


@router.post("/{camera_id}/disconnect")
def disconnect_camera(camera_id: str) -> dict[str, Any]:
    return camera_service.disconnect(camera_id)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: str) -> None:
    camera_service.delete(camera_id)


@router.get("/{camera_id}/video")
def camera_video(camera_id: str) -> StreamingResponse:
    return StreamingResponse(
        camera_service.frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
