from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.container import Container, get_container


router = APIRouter(prefix="/api/identification", tags=["identification"])


@router.get("/logs")
def identification_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    return container.identification_service.logs(page, page_size)
