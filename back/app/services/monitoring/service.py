from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from app.infra.ai.pet_identifier import PetIdentifier
from app.infra.ai.yolox_detector import YoloXDetector
from app.infra.camera.manager import CameraManager
from app.infra.media.clip_store import ClipStore
from app.infra.media.pet_image_store import PetImageStore
from app.infra.media.snapshot_store import SnapshotStore
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.services.monitoring.clips import ClipRecorder
from app.services.monitoring.events import EventRecorder
from app.services.monitoring.tracking import ZoneTracker

logger = logging.getLogger(__name__)

PROVIDER = "opencv-yolox-tiny"
LOOP_INTERVAL_SECONDS = 0.35


class MonitoringService:
    def __init__(
        self,
        camera_manager: CameraManager,
        zone_repository: ZoneRepository,
        event_repository: EventRepository,
        snapshot_store: SnapshotStore,
        clip_store: ClipStore,
        detector: YoloXDetector | None,
        model_error: str | None = None,
        pet_image_store: PetImageStore | None = None,
        pet_identifier: PetIdentifier | None = None,
    ) -> None:
        self.camera_manager = camera_manager
        self.zone_repository = zone_repository
        self.detector = detector
        self.model_error = model_error
        self.events = EventRecorder(event_repository, snapshot_store, camera_manager, pet_image_store, pet_identifier)
        self.tracker = ZoneTracker(ClipRecorder(clip_store, event_repository), self.events, pet_image_store)
        self._feedback: dict[str, dict[str, Any]] = {}
        self._feedback_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_error: str | None = model_error

    def start(self) -> None:
        self.events.close_all_open(datetime.now(timezone.utc))
        if self.detector is None or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ai-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        stopped_at = datetime.now(timezone.utc)
        self.tracker.finalize_clips(stopped_at)
        self.events.close_all_open(stopped_at)

    def health(self) -> dict[str, Any]:
        if self.detector is None:
            return {"status": "model_missing", "provider": PROVIDER, "error": self._last_error}
        return {
            "status": "running" if self._thread and self._thread.is_alive() else "stopped",
            "provider": PROVIDER,
            "error": self._last_error,
        }

    def feedback(self, camera_id: str) -> dict[str, Any]:
        with self._feedback_lock:
            current = self._feedback.get(camera_id)
            if current:
                return current
        return self._feedback_payload(camera_id, self.health()["status"], error=self._last_error, updated=False)

    def _run(self) -> None:
        while not self._stop.wait(LOOP_INTERVAL_SECONDS):
            camera_ids = list(dict.fromkeys([*self.camera_manager.connected_ids(), *self.tracker.runtimes]))
            for camera_id in camera_ids:
                if self._stop.is_set():
                    return
                self._process_camera(camera_id)

    def _process_camera(self, camera_id: str) -> None:
        if self.detector is None:
            return
        frame = self.camera_manager.latest_frame(camera_id)
        if frame is None:
            self._process_offline_camera(camera_id)
            return
        try:
            detections = self.detector.detect(frame)
            self._last_error = None
            zones = self.zone_repository.list(camera_id)
            feedback_zones = self.tracker.track(camera_id, frame, zones, detections)
            self._publish(camera_id, "running", detections=[detection.as_dict() for detection in detections], zones=feedback_zones)
        except Exception as error:
            if str(error) != self._last_error:
                logger.exception("Falha no ciclo de inferência da câmera %s", camera_id)
            self._last_error = str(error)
            self._publish(camera_id, "error", error=str(error))

    def _process_offline_camera(self, camera_id: str) -> None:
        if not self.tracker.has_state(camera_id):
            return
        try:
            zones = self.zone_repository.list(camera_id)
            feedback_zones = self.tracker.track(camera_id, None, zones, [])
        except Exception:
            logger.exception("Falha ao encerrar áreas da câmera desconectada %s", camera_id)
            return
        self._publish(camera_id, "stopped", zones=feedback_zones)
        if self.tracker.idle(camera_id):
            self.tracker.forget(camera_id)

    def _publish(
        self,
        camera_id: str,
        status: str,
        detections: list[dict[str, Any]] | None = None,
        zones: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        payload = self._feedback_payload(camera_id, status, detections, zones, error)
        with self._feedback_lock:
            self._feedback[camera_id] = payload

    @staticmethod
    def _feedback_payload(
        camera_id: str,
        status: str,
        detections: list[dict[str, Any]] | None = None,
        zones: list[dict[str, Any]] | None = None,
        error: str | None = None,
        updated: bool = True,
    ) -> dict[str, Any]:
        return {
            "camera_id": camera_id,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat() if updated else None,
            "detections": detections or [],
            "zones": zones or [],
            "error": error,
        }
