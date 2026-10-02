from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import FRONTEND_DIST


router = APIRouter(include_in_schema=False)


@router.get("/")
def index() -> FileResponse:
    index_file = FRONTEND_DIST / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=503, detail="Interface ainda não foi compilada. Execute o build do front.")
    return FileResponse(index_file)


@router.get("/{path:path}")
def spa_fallback(path: str) -> FileResponse:
    candidate = (FRONTEND_DIST / Path(path)).resolve()
    if FRONTEND_DIST.resolve() in candidate.parents and candidate.is_file():
        return FileResponse(candidate)
    return index()
