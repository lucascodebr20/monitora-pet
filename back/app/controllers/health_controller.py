from typing import Any

from fastapi import APIRouter, Depends

from app.core.container import Container, get_container


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.health_service.health()


@router.get("/dashboard")
def dashboard(container: Container = Depends(get_container)) -> dict[str, Any]:
    return container.health_service.dashboard()
