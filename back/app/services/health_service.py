from datetime import datetime, timezone
from typing import Any

from app.core.config import APP_VERSION
from app.infra.repositories.event_repository import EventRepository
from app.services.camera_service import CameraService
from app.services.event_service import EventService


class HealthService:
    def __init__(
        self,
        camera_service: CameraService,
        event_service: EventService,
        event_repository: EventRepository,
    ) -> None:
        self.camera_service = camera_service
        self.event_service = event_service
        self.event_repository = event_repository

    def health(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "version": APP_VERSION,
            "database": "available",
            "cameras": self.camera_service.health(),
            "inference": {"status": "not_configured", "provider": None},
        }

    def dashboard(self) -> dict[str, Any]:
        today = datetime.now(timezone.utc).date().isoformat()
        return {
            "date": today,
            "events_today": self.event_repository.count_on_date(today),
            "pending_reviews": self.event_repository.count_pending_reviews(),
            "by_zone_type": self.event_repository.count_by_zone_type_on_date(today),
            "recent_events": self.event_service.list(limit=6),
            "health": self.health(),
        }
