from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.controllers.schemas.event_schema import HighlightUpdateRequest, ReviewCreateRequest
from app.core.container import Container, get_container
from app.domain.enums import ZoneType


router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def get_events(
    camera_id: str | None = None,
    zone_id: str | None = None,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    pending_review: bool = False,
    highlighted: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=500),
    pet_id: str | None = None,
    zone_type: ZoneType | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    return container.event_query_service.search(
        page=page,
        page_size=limit or page_size,
        pet_id=pet_id,
        zone_type=zone_type,
        pending_review=pending_review,
        camera_id=camera_id,
        zone_id=zone_id,
        date=date,
        start_date=start_date,
        end_date=end_date,
        highlighted=highlighted,
    )


@router.post("/{event_id}/reviews", status_code=201)
def review_event(
    event_id: str, request: ReviewCreateRequest, container: Container = Depends(get_container)
) -> dict[str, Any]:
    return container.event_review_service.review(event_id, request.to_command())


@router.put("/{event_id}/highlight")
def highlight_event(
    event_id: str, request: HighlightUpdateRequest, container: Container = Depends(get_container)
) -> dict[str, Any]:
    return container.event_highlight_service.set_highlighted(event_id, request.highlighted)


@router.get("/{event_id}/snapshot")
def event_snapshot(event_id: str, container: Container = Depends(get_container)) -> FileResponse:
    return FileResponse(container.event_media_service.snapshot(event_id), media_type="image/jpeg")


@router.get("/{event_id}/clip")
def event_clip(event_id: str, container: Container = Depends(get_container)) -> FileResponse:
    return FileResponse(container.event_media_service.clip(event_id), media_type="video/webm")
