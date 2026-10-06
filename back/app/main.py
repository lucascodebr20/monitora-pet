import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.controllers.auth_controller import router as auth_router
from app.controllers.camera_controller import router as camera_router
from app.controllers.event_controller import router as event_router
from app.controllers.health_controller import router as health_router
from app.controllers.identification_controller import router as identification_router
from app.controllers.job_controller import router as job_router
from app.controllers.monitoring_controller import router as monitoring_router
from app.controllers.notice_controller import router as notice_router
from app.controllers.pet_controller import router as pet_router
from app.controllers.recording_controller import router as recording_router
from app.controllers.web_controller import router as web_router
from app.controllers.zone_controller import router as zone_router
from app.core.config import APP_NAME, APP_VERSION, Settings
from app.core.container import build_container
from app.core.logging_setup import configure_logging
from app.core.security import install_access_control
from app.domain.errors import (
    EntityConflictError,
    EntityNotFoundError,
    InvalidDomainValueError,
    OperationFailedError,
)

logger = logging.getLogger(__name__)

ERROR_STATUS = {
    EntityNotFoundError: 404,
    EntityConflictError: 409,
    InvalidDomainValueError: 422,
    OperationFailedError: 422,
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_directories()
        log_file = configure_logging(settings.log_dir)
        logger.info("%s %s iniciando; dados em %s; log em %s", APP_NAME, APP_VERSION, settings.data_dir, log_file)
        container = build_container(settings, on_job_state=_announce_job_state)
        container.database.migrate()
        container.monitoring_service.start()
        app.state.container = container
        threading.Thread(target=container.camera_service.reconnect_all, name="camera-reconnect", daemon=True).start()
        container.import_worker.start()
        logger.info("Inferência: %s", container.monitoring_service.health())
        yield
        logger.info("Encerrando: parando inferência e desconectando câmeras")
        container.import_worker.stop()
        container.monitoring_service.stop()
        container.camera_manager.disconnect_all()

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    install_access_control(app)

    for error_type, status_code in ERROR_STATUS.items():
        app.add_exception_handler(error_type, _domain_error_handler(status_code))

    if (settings.frontend_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=settings.frontend_dist / "assets"), name="assets")

    for router in (
        auth_router,
        health_router,
        identification_router,
        camera_router,
        zone_router,
        event_router,
        pet_router,
        recording_router,
        job_router,
        notice_router,
        monitoring_router,
        web_router,
    ):
        app.include_router(router)
    return app


def _announce_job_state(status: str) -> None:
    print(f"VIGIAPET_JOB={status}", flush=True)


def _domain_error_handler(status_code: int):
    async def handler(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handler


app = create_app()
