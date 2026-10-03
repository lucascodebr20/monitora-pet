from typing import Any

from fastapi import APIRouter, Query

from app.core.container import pet_identifier


router = APIRouter(prefix="/api/identification", tags=["identification"])


@router.get("/logs")
def identification_logs(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return pet_identifier.logs(limit)
