from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Request

from app.core.config import Settings
from app.infra.ai.identification_calibration import IdentificationCalibrator
from app.infra.ai.pet_identifier import PetIdentifier
from app.infra.ai.yolox_detector import YoloXDetector
from app.infra.camera.manager import CameraManager
from app.infra.database.database import Database
from app.infra.media.clip_store import ClipStore
from app.infra.media.media_cleanup import MediaCleanup
from app.infra.media.pet_image_store import PetImageStore
from app.infra.media.snapshot_store import SnapshotStore
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.monitoring_session_repository import MonitoringSessionRepository
from app.infra.repositories.notice_repository import NoticeRepository
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.infra.repositories.pet_repository import PetRepository
from app.infra.repositories.recording_repository import RecordingRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.services import (
    CameraDiscoveryService,
    CameraService,
    EventMediaService,
    EventPurgeService,
    EventQueryService,
    EventReviewService,
    HealthService,
    IdentificationService,
    MonitoringService,
    NoticeService,
    PetService,
    RecordingAnalyzer,
    RecordingImportService,
    ZoneService,
)

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    database: Database
    camera_manager: CameraManager
    camera_service: CameraService
    camera_discovery_service: CameraDiscoveryService
    zone_service: ZoneService
    pet_service: PetService
    event_query_service: EventQueryService
    event_review_service: EventReviewService
    event_media_service: EventMediaService
    identification_service: IdentificationService
    monitoring_service: MonitoringService
    health_service: HealthService
    notice_service: NoticeService
    recording_import_service: RecordingImportService
    recording_analyzer: RecordingAnalyzer | None


def build_container(settings: Settings) -> Container:
    database = Database(settings.database_path)
    camera_manager = CameraManager()
    snapshot_store = SnapshotStore(settings.data_dir, settings.snapshot_dir)
    clip_store = ClipStore(settings.data_dir, settings.clip_dir)
    pet_image_store = PetImageStore(settings.data_dir, settings.pet_image_dir)

    camera_repository = CameraRepository(database)
    zone_repository = ZoneRepository(database)
    event_repository = EventRepository(database)
    pet_repository = PetRepository(database)
    pet_identification_repository = PetIdentificationRepository(database)
    notice_repository = NoticeRepository(database)
    session_repository = MonitoringSessionRepository(database)
    recording_repository = RecordingRepository(database)
    purge_service = EventPurgeService(event_repository, recording_repository, MediaCleanup(settings.data_dir))

    pet_identifier = PetIdentifier(
        pet_repository, pet_image_store, pet_identification_repository, settings.embedding_model_path
    )
    identification_calibrator = IdentificationCalibrator(pet_identification_repository)
    detector, model_error = _load_detector(settings)

    camera_service = CameraService(camera_repository, camera_manager, purge_service)
    event_query_service = EventQueryService(event_repository)
    monitoring_service = MonitoringService(
        camera_manager,
        zone_repository,
        event_repository,
        snapshot_store,
        clip_store,
        detector,
        model_error,
        pet_image_store,
        pet_identifier,
        session_repository=session_repository,
    )
    recording_analyzer = (
        RecordingAnalyzer(
            detector,
            zone_repository,
            event_repository,
            snapshot_store,
            clip_store,
            session_repository,
            recording_repository,
            pet_image_store,
            pet_identifier,
        )
        if detector
        else None
    )
    return Container(
        settings=settings,
        database=database,
        camera_manager=camera_manager,
        camera_service=camera_service,
        camera_discovery_service=CameraDiscoveryService(camera_repository),
        zone_service=ZoneService(zone_repository, camera_service, purge_service),
        pet_service=PetService(pet_repository, pet_image_store),
        event_query_service=event_query_service,
        event_review_service=EventReviewService(event_repository, pet_repository, identification_calibrator),
        event_media_service=EventMediaService(event_repository, snapshot_store, clip_store),
        identification_service=IdentificationService(pet_identification_repository, identification_calibrator),
        monitoring_service=monitoring_service,
        health_service=HealthService(camera_service, event_query_service, event_repository, monitoring_service),
        notice_service=NoticeService(notice_repository),
        recording_import_service=RecordingImportService(recording_repository, camera_service, purge_service),
        recording_analyzer=recording_analyzer,
    )


def _load_detector(settings: Settings) -> tuple[YoloXDetector | None, str | None]:
    if not settings.model_path.exists():
        logger.warning("Modelo YOLOX-Tiny não encontrado em %s; a inferência ficará desativada", settings.model_path)
        return None, "Modelo YOLOX-Tiny não encontrado."
    try:
        return YoloXDetector(settings.model_path), None
    except Exception as error:
        logger.exception("Falha ao carregar o modelo YOLOX em %s", settings.model_path)
        return None, str(error)


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
