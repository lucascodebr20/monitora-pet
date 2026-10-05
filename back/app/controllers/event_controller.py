from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.controllers.schemas.event_schema import ReviewCreateRequest
from app.core.container import event_media_service, event_query_service, event_review_service
from app.domain.enums import ZoneType


router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def get_events(
    camera_id: str | None = None,
    zone_id: str | None = None,
    date: str | None = None,
    pending_review: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=500),
    pet_id: str | None = None,
    zone_type: ZoneType | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
) -> dict[str, Any]:
    return event_query_service.search(
        page,
        limit or page_size,
        pet_id,
        zone_type,
        pending_review,
        camera_id,
        zone_id,
        date,
    )


@router.post("/{event_id}/reviews", status_code=201)
def review_event(event_id: str, request: ReviewCreateRequest) -> dict[str, Any]:
    return event_review_service.review(event_id, request.to_command())


@router.get("/{event_id}/snapshot")
def event_snapshot(event_id: str) -> FileResponse:
    return FileResponse(event_media_service.snapshot(event_id), media_type="image/jpeg")


@router.get("/{event_id}/clip")
def event_clip(event_id: str) -> FileResponse:
    return FileResponse(event_media_service.clip(event_id), media_type="video/webm")
