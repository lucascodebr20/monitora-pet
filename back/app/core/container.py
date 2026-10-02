from app.core.config import DATABASE_PATH, MODEL_PATH
from app.infra.ai.yolox_detector import YoloXDetector
from app.infra.camera.manager import CameraManager
from app.infra.database.database import Database
from app.infra.media.clip_store import ClipStore
from app.infra.repositories.camera_repository import CameraRepository
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.notice_repository import NoticeRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.infra.media.snapshot_store import SnapshotStore
from app.services.camera_service import CameraService
from app.services.event_service import EventService
from app.services.health_service import HealthService
from app.services.notice_service import NoticeService
from app.services.monitoring_service import MonitoringService
from app.services.zone_service import ZoneService


database = Database(DATABASE_PATH)
camera_manager = CameraManager()
snapshot_store = SnapshotStore()
clip_store = ClipStore()

camera_repository = CameraRepository(database)
zone_repository = ZoneRepository(database)
event_repository = EventRepository(database)
notice_repository = NoticeRepository(database)

camera_service = CameraService(camera_repository, camera_manager)
zone_service = ZoneService(zone_repository, camera_service)
event_service = EventService(event_repository, snapshot_store, clip_store)
model_error = None
detector = None
if MODEL_PATH.exists():
    try:
        detector = YoloXDetector(MODEL_PATH)
    except Exception as error:
        model_error = str(error)
else:
    model_error = "Modelo YOLOX-Tiny não encontrado."
monitoring_service = MonitoringService(
    camera_manager,
    zone_repository,
    event_repository,
    snapshot_store,
    clip_store,
    detector,
    model_error,
)
health_service = HealthService(camera_service, event_service, event_repository, monitoring_service)
notice_service = NoticeService(notice_repository)
