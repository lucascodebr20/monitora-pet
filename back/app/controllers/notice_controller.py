from typing import Any

from fastapi import APIRouter, Depends

from app.core.container import Container, get_container


router = APIRouter(prefix="/api/notices", tags=["notices"])


@router.get("")
def notices(container: Container = Depends(get_container)) -> dict[str, Any]:
    return {"notices": container.notice_service.active()}
