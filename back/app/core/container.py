from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

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
from app.infra.repositories.event_highlight_repository import EventHighlightRepository
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.monitoring_session_repository import MonitoringSessionRepository
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.infra.repositories.pet_repository import PetRepository
from app.infra.repositories.recording_repository import RecordingRepository
from app.infra.repositories.settings_repository import SettingsRepository
from app.services.event.auto_review import AutoReviewService
from app.infra.repositories.watched_folder_repository import WatchedFolderRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.infra.security.credential_store import CredentialStore
from app.services import (
    CameraDiscoveryService,
    CameraPreviewService,
    CameraProfileService,
    CameraRecordingSync,
    CameraService,
    EventHighlightService,
    EventMediaService,
    EventPurgeService,
    EventQueryService,
    EventReviewService,
    HealthService,
    HouseholdService,
    IdentificationService,
    ImportWorker,
    MediaRetentionService,
    MonitoringService,
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
    event_highlight_service: EventHighlightService
    identification_service: IdentificationService
    monitoring_service: MonitoringService
    health_service: HealthService
    retention_service: MediaRetentionService
    household_service: HouseholdService
    auto_review_service: AutoReviewService
    recording_import_service: RecordingImportService
    recording_analyzer: RecordingAnalyzer | None
    camera_recording_sync: CameraRecordingSync
    camera_preview_service: CameraPreviewService
    watched_folder_repository: WatchedFolderRepository
    settings_repository: SettingsRepository
    import_worker: ImportWorker


def build_container(settings: Settings, on_job_state: Callable[[str], None] | None = None) -> Container:
    database = Database(settings.database_path)
    camera_manager = CameraManager()
    snapshot_store = SnapshotStore(settings.data_dir, settings.snapshot_dir)
    clip_store = ClipStore(settings.data_dir, settings.clip_dir)
    pet_image_store = PetImageStore(settings.data_dir, settings.pet_image_dir)

    camera_repository = CameraRepository(database)
    zone_repository = ZoneRepository(database)
    event_repository = EventRepository(database)
    event_highlight_repository = EventHighlightRepository(database)
    pet_repository = PetRepository(database)
    pet_identification_repository = PetIdentificationRepository(database)
    session_repository = MonitoringSessionRepository(database)
    recording_repository = RecordingRepository(database)
    watched_folder_repository = WatchedFolderRepository(database)
    settings_repository = SettingsRepository(database)
    media_cleanup = MediaCleanup(settings.data_dir)
    purge_service = EventPurgeService(event_repository, recording_repository, media_cleanup)
    retention_service = MediaRetentionService(settings_repository, event_repository, recording_repository, media_cleanup)
    auto_review_service = AutoReviewService(settings_repository, event_repository, pet_identification_repository)

    pet_identifier = PetIdentifier(
        pet_repository, pet_image_store, pet_identification_repository, settings.embedding_model_path
    )
    identification_calibrator = IdentificationCalibrator(pet_identification_repository)
    detector, model_error = _load_detector(settings)

    camera_profile = CameraProfileService(camera_repository, CredentialStore(settings.data_dir))
    camera_service = CameraService(camera_repository, camera_manager, purge_service, camera_profile)
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
        auto_review=auto_review_service,
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
            purge_service,
            pet_image_store,
            pet_identifier,
            auto_review=auto_review_service,
        )
        if detector
        else None
    )
    recording_import_service = RecordingImportService(
        recording_repository, camera_service, purge_service, folders=watched_folder_repository
    )
    camera_recording_sync = CameraRecordingSync(
        camera_repository,
        session_repository,
        recording_repository,
        camera_profile,
        recording_import_service,
        settings.recordings_dir,
    )
    import_worker = ImportWorker(
        recording_import_service, recording_analyzer, camera_recording_sync, recording_repository, camera_repository,
        on_state=on_job_state, maintenance=retention_service.run,
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
        event_highlight_service=EventHighlightService(event_repository, event_highlight_repository),
        identification_service=IdentificationService(pet_identification_repository, identification_calibrator),
        monitoring_service=monitoring_service,
        health_service=HealthService(camera_service, event_query_service, event_repository, monitoring_service),
        retention_service=retention_service,
        household_service=HouseholdService(settings_repository),
        auto_review_service=auto_review_service,
        recording_import_service=recording_import_service,
        recording_analyzer=recording_analyzer,
        camera_recording_sync=camera_recording_sync,
        import_worker=import_worker,
        camera_preview_service=CameraPreviewService(camera_service, camera_manager, recording_repository),
        watched_folder_repository=watched_folder_repository,
        settings_repository=settings_repository,
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
