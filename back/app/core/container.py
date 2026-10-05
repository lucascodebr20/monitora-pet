import logging

from app.core.config import DATABASE_PATH, MODEL_PATH
from app.infra.ai.yolox_detector import YoloXDetector
from app.infra.ai.pet_identifier import PetIdentifier
from app.infra.camera.manager import CameraManager
from app.infra.database.database import Database
from app.infra.media.clip_store import ClipStore
from app.infra.media.pet_image_store import PetImageStore
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.notice_repository import NoticeRepository
from app.infra.repositories.pet_repository import PetRepository
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.infra.media.snapshot_store import SnapshotStore
from app.services.camera_service import CameraService
from app.services.event_service import EventService
from app.services.health_service import HealthService
from app.services.identification_service import IdentificationService
from app.services.notice_service import NoticeService
from app.services.pet_service import PetService
from app.services.monitoring import MonitoringService
from app.services.zone_service import ZoneService


database = Database(DATABASE_PATH)
camera_manager = CameraManager()
snapshot_store = SnapshotStore()
clip_store = ClipStore()
pet_image_store = PetImageStore()

camera_repository = CameraRepository(database)
zone_repository = ZoneRepository(database)
event_repository = EventRepository(database)
pet_repository = PetRepository(database)
pet_identification_repository = PetIdentificationRepository(database)
pet_identifier = PetIdentifier(pet_repository, pet_image_store, pet_identification_repository)
notice_repository = NoticeRepository(database)

camera_service = CameraService(camera_repository, camera_manager)
zone_service = ZoneService(zone_repository, camera_service)
pet_service = PetService(pet_repository, pet_image_store)
event_service = EventService(event_repository, snapshot_store, clip_store, pet_repository, pet_image_store, pet_identifier)
logger = logging.getLogger(__name__)
model_error = None
detector = None
if MODEL_PATH.exists():
    try:
        detector = YoloXDetector(MODEL_PATH)
    except Exception as error:
        model_error = str(error)
        logger.exception("Falha ao carregar o modelo YOLOX em %s", MODEL_PATH)
else:
    model_error = "Modelo YOLOX-Tiny não encontrado."
    logger.warning("Modelo YOLOX-Tiny não encontrado em %s; a inferência ficará desativada", MODEL_PATH)
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
)
health_service = HealthService(camera_service, event_service, event_repository, monitoring_service)
notice_service = NoticeService(notice_repository)
identification_service = IdentificationService(pet_identifier)
