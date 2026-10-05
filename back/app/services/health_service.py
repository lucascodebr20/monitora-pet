from typing import Any

from app.core.config import APP_VERSION
from app.domain.clock import local_today
from app.infra.repositories.event_repository import EventRepository
from app.services.camera_service import CameraService
from app.services.event_service import EventService
from app.services.monitoring import MonitoringService


class HealthService:
    def __init__(
        self,
        camera_service: CameraService,
        event_service: EventService,
        event_repository: EventRepository,
        monitoring_service: MonitoringService,
    ) -> None:
        self.camera_service = camera_service
        self.event_service = event_service
        self.event_repository = event_repository
        self.monitoring_service = monitoring_service

    def health(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "version": APP_VERSION,
            "database": "available",
            "cameras": self.camera_service.health(),
            "inference": self.monitoring_service.health(),
        }

    def dashboard(self) -> dict[str, Any]:
        today = local_today().isoformat()
        return {
            "date": today,
            "events_today": self.event_repository.count_on_date(today),
            "pending_reviews": self.event_repository.count_pending_reviews(),
            "by_zone_type": self.event_repository.count_by_zone_type_on_date(today),
            "recent_events": self.event_service.list(limit=6),
            "health": self.health(),
        }
