from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from app.controllers.schemas.recording_schema import RecordingImportRequest, RecordingTimeRequest, WatchedFolderRequest
from app.core.container import Container, get_container
from app.domain.errors import EntityNotFoundError

router = APIRouter(prefix="/api/recordings", tags=["recordings"])


@router.get("")
def list_recordings(
    camera_id: str | None = None, status: str | None = None, container: Container = Depends(get_container)
) -> dict[str, Any]:
    return {"recordings": container.recording_import_service.list(camera_id, status)}


@router.post("/import", status_code=201)
def import_recordings(request: RecordingImportRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    importer = container.recording_import_service
    path = Path(request.path)
    if request.started_at is not None and path.is_file():
        recordings = [importer.register(request.camera_id, path, request.started_at, time_source="MANUAL")]
    else:
        recordings = importer.import_path(request.camera_id, path)
    return {"recordings": recordings}


@router.post("/{recording_id}/reprocess")
def reprocess_recording(recording_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.recording_import_service.reprocess(recording_id)


@router.patch("/{recording_id}")
def adjust_recording_time(
    recording_id: str, request: RecordingTimeRequest, container: Container = Depends(get_container)
) -> dict[str, Any]:
    return container.recording_import_service.adjust_start(recording_id, request.started_at)


@router.get("/folders")
def list_folders(camera_id: str | None = None, container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"folders": container.watched_folder_repository.list(camera_id)}


@router.post("/folders", status_code=201)
def create_folder(request: WatchedFolderRequest, container: Container = Depends(get_container)) -> dict[str, Any]:
    container.camera_service.get(request.camera_id)
    if not Path(request.path).is_dir():
        raise EntityNotFoundError("A pasta informada não foi encontrada.")
    return container.watched_folder_repository.create(request.camera_id, request.path)


@router.delete("/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: str, container: Container = Depends(get_container)) -> None:
    if not container.watched_folder_repository.get(folder_id):
        raise EntityNotFoundError("Pasta vigiada não encontrada.")
    container.watched_folder_repository.delete(folder_id)


@router.post("/folders/{folder_id}/scan")
def scan_folder(folder_id: str, container: Container = Depends(get_container)) -> dict[str, Any]:
    folder = container.watched_folder_repository.get(folder_id)
    if not folder:
        raise EntityNotFoundError("Pasta vigiada não encontrada.")
    recordings = container.recording_import_service.scan_folder(folder["camera_id"], Path(folder["path"]))
    container.watched_folder_repository.mark_scanned(folder_id)
    return {"recordings": recordings}
