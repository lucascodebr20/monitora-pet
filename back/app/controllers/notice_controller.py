from typing import Any

from fastapi import APIRouter

from app.core.container import notice_service


router = APIRouter(prefix="/api/notices", tags=["notices"])


@router.get("")
def notices() -> dict[str, Any]:
    return {"notices": notice_service.active()}
