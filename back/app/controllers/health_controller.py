from typing import Any

from fastapi import APIRouter

from app.core.container import health_service


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, Any]:
    return health_service.health()


@router.get("/dashboard")
def dashboard() -> dict[str, Any]:
    return health_service.dashboard()
