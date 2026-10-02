from typing import Any

from fastapi import APIRouter, Query

from app.controllers.schemas.event_schema import ReviewCreateRequest
from app.core.container import event_service


router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def get_events(
    camera_id: str | None = None,
    zone_id: str | None = None,
    date: str | None = None,
    pending_review: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return {"events": event_service.list(camera_id, zone_id, date, pending_review, limit)}


@router.post("/{event_id}/reviews", status_code=201)
def review_event(event_id: str, request: ReviewCreateRequest) -> dict[str, Any]:
    return event_service.review(event_id, request.to_command())
