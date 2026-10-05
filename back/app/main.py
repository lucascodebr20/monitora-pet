from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import APP_NAME, APP_VERSION, FRONTEND_DIST, ensure_data_directories
from app.core.container import camera_manager, database, monitoring_service
from app.core.security import ALLOWED_HOSTS, require_session
from app.controllers.auth_controller import router as auth_router
from app.controllers.camera_controller import router as camera_router
from app.controllers.event_controller import router as event_router
from app.controllers.health_controller import router as health_router
from app.controllers.identification_controller import router as identification_router
from app.controllers.notice_controller import router as notice_router
from app.controllers.pet_controller import router as pet_router
from app.controllers.monitoring_controller import router as monitoring_router
from app.controllers.web_controller import router as web_router
from app.controllers.zone_controller import router as zone_router
from app.domain.errors import (
    EntityConflictError,
    EntityNotFoundError,
    InvalidDomainValueError,
    OperationFailedError,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_data_directories()
    database.migrate()
    monitoring_service.start()
    yield
    monitoring_service.stop()
    camera_manager.disconnect_all()


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Rejeita cabeçalhos Host que não sejam locais (bloqueia DNS rebinding).
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


@app.exception_handler(EntityNotFoundError)
async def entity_not_found(_: Request, error: EntityNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(EntityConflictError)
async def entity_conflict(_: Request, error: EntityConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(error)})


@app.exception_handler(InvalidDomainValueError)
async def invalid_domain_value(_: Request, error: InvalidDomainValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(error)})


@app.exception_handler(OperationFailedError)
async def operation_failed(_: Request, error: OperationFailedError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(error)})


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

# Toda rota /api/* exige sessão quando MONITORAPET_API_TOKEN está definido.
# /api/session fica fora porque é o próprio ponto de entrada da sessão.
protected = [Depends(require_session)]

app.include_router(auth_router)
app.include_router(health_router, dependencies=protected)
app.include_router(identification_router, dependencies=protected)
app.include_router(camera_router, dependencies=protected)
app.include_router(zone_router, dependencies=protected)
app.include_router(event_router, dependencies=protected)
app.include_router(pet_router, dependencies=protected)
app.include_router(notice_router, dependencies=protected)
app.include_router(monitoring_router, dependencies=protected)
app.include_router(web_router)
