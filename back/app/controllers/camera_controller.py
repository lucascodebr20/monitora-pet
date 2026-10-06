from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse

from app.controllers.schemas.camera_schema import (
    CameraConvertRequest,
    CameraCreateRequest,
    CameraCredentialsRequest,
    ManualCameraCreateRequest,
)
from app.core.container import Container, get_container


router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("/discover")
def discover_cameras(fallback: bool = False, container: Container = Depends(get_container)) -> dict[str, object]:
    return {"cameras": container.camera_discovery_service.discover(fallback)}


@router.get("")
def list_cameras(container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"cameras": container.camera_service.list()}


@router.post("", status_code=201)
def create_camera(request: CameraCreateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.camera_service.create(request.to_command())


@router.post("/manual", status_code=201)
def create_manual_camera(request: ManualCameraCreateRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.camera_service.create_manual(request.name)


@router.post("/{camera_id}/convert")
def convert_camera(
    camera_id: str, request: CameraConvertRequest, container: Container = Depends(get_container)
) -> dict[str, Any]:
    return container.camera_service.convert_to_network(camera_id, request.to_command())


@router.get("/{camera_id}/preview")
def camera_preview(camera_id: str, container: Container = Depends(get_container)) -> Response:
    return Response(container.camera_preview_service.preview(camera_id), media_type="image/jpeg")


@router.post("/{camera_id}/connect")
def connect_camera(
    camera_id: str, credentials: CameraCredentialsRequest, container: Container = Depends(get_container)
) -> dict[str, Any]:
    return container.camera_service.connect(camera_id, credentials.to_command())


@router.post("/{camera_id}/disconnect")
def disconnect_camera(camera_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.camera_service.disconnect(camera_id)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: str, container: Container = Depends(get_container)) -> None:
    container.camera_service.delete(camera_id)


@router.get("/{camera_id}/video")
def camera_video(camera_id: str, container: Container = Depends(get_container)) -> StreamingResponse:
    return StreamingResponse(
        container.camera_service.frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
