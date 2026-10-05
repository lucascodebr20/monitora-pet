from typing import Any

from fastapi import APIRouter, Query

from app.core.container import identification_service


router = APIRouter(prefix="/api/identification", tags=["identification"])


@router.get("/logs")
def identification_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    return identification_service.logs(page, page_size)
