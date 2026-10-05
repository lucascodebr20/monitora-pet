from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import APP_NAME, APP_VERSION, FRONTEND_DIST, ensure_data_directories
from app.core.container import camera_manager, database, monitoring_service
from app.core.security import install_access_control
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
    openapi_url="/api/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)

# Host local obrigatório (bloqueia DNS rebinding) e sessão exigida em todo /api/* quando
# MONITORAPET_API_TOKEN está definido. Só /api/session fica público, por ser a porta de entrada.
install_access_control(app)


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

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(identification_router)
app.include_router(camera_router)
app.include_router(zone_router)
app.include_router(event_router)
app.include_router(pet_router)
app.include_router(notice_router)
app.include_router(monitoring_router)
app.include_router(web_router)
