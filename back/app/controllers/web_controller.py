from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.core.container import get_settings


router = APIRouter(include_in_schema=False)


@router.get("/")
def index(settings: Settings = Depends(get_settings)) -> FileResponse:
    return _index(settings)


@router.get("/{path:path}")
def spa_fallback(path: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Rota não encontrada.")
    candidate = (settings.frontend_dist / Path(path)).resolve()
    if settings.frontend_dist.resolve() in candidate.parents and candidate.is_file():
        return FileResponse(candidate)
    return _index(settings)


def _index(settings: Settings) -> FileResponse:
    index_file = settings.frontend_dist / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=503, detail="Interface ainda não foi compilada. Execute o build do front.")
    return FileResponse(index_file)
