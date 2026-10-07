from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from app.domain.clock import Clock, Moment, SystemClock
from app.infra.ai.pet_identifier import PetIdentifier
from app.infra.camera.manager import CameraManager
from app.infra.media.clip_store import ClipStore
from app.infra.media.pet_image_store import PetImageStore
from app.infra.media.snapshot_store import SnapshotStore
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.monitoring_session_repository import MonitoringSessionRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.services.monitoring.analysis import Detector, FrameAnalyzer
from app.services.monitoring.clips import ClipRecorder
from app.services.monitoring.coverage import CoverageRecorder
from app.services.monitoring.events import EventRecorder
from app.services.monitoring.snapshots import StreamSnapshotSource
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
        detector: Detector | None,
        model_error: str | None = None,
        pet_image_store: PetImageStore | None = None,
        pet_identifier: PetIdentifier | None = None,
        clock: Clock | None = None,
        session_repository: MonitoringSessionRepository | None = None,
    ) -> None:
        self.camera_manager = camera_manager
        self.coverage = CoverageRecorder(session_repository) if session_repository else None
        self.detector = detector
        self.model_error = model_error
        self.clock = clock or SystemClock()
        self.events = EventRecorder(
            event_repository, snapshot_store, StreamSnapshotSource(camera_manager), pet_image_store, pet_identifier
        )
        self.tracker = ZoneTracker(ClipRecorder(clip_store, event_repository), self.events, pet_image_store)
        self.analyzer = FrameAnalyzer(detector, zone_repository, self.tracker) if detector else None
        self._feedback: dict[str, dict[str, Any]] = {}
        self._feedback_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_error: str | None = model_error

    def start(self) -> None:
        self.events.close_all_open(self.clock.now().utc)
        if self.analyzer is None or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ai-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        stopped_at = self.clock.now().utc
        self.tracker.finalize_clips(stopped_at)
        self.events.close_all_open(stopped_at)
        if self.coverage:
            self.coverage.close_all()

    def health(self) -> dict[str, Any]:
        if self.analyzer is None:
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
        return self._feedback_payload(camera_id, self.health()["status"], error=self._last_error)

    def _run(self) -> None:
        while not self._stop.wait(LOOP_INTERVAL_SECONDS):
            camera_ids = list(dict.fromkeys([*self.camera_manager.connected_ids(), *self.tracker.runtimes]))
            for camera_id in camera_ids:
                if self._stop.is_set():
                    return
                self._process_camera(camera_id)

    def _process_camera(self, camera_id: str) -> None:
        if self.analyzer is None:
            return
        moment = self.clock.now()
        frame = self.camera_manager.latest_frame(camera_id)
        if frame is None:
            if self.coverage:
                self.coverage.close(camera_id)
            self._process_offline_camera(camera_id, moment)
            return
        try:
            analysis = self.analyzer.analyze(camera_id, frame, moment)
            if self.coverage:
                self.coverage.observe(camera_id, moment.utc)
            self._last_error = None
            detections = [detection.as_dict() for detection in analysis.detections]
            self._publish(camera_id, "running", moment, detections=detections, zones=analysis.zones)
        except Exception as error:
            if self.coverage:
                self.coverage.close(camera_id)
            if str(error) != self._last_error:
                logger.exception("Falha no ciclo de inferência da câmera %s", camera_id)
            self._last_error = str(error)
            self._publish(camera_id, "error", moment, error=str(error))

    def _process_offline_camera(self, camera_id: str, moment: Moment) -> None:
        if self.analyzer is None or not self.tracker.has_state(camera_id):
            return
        try:
            feedback_zones = self.analyzer.absence(camera_id, moment)
        except Exception:
            logger.exception("Falha ao encerrar áreas da câmera desconectada %s", camera_id)
            return
        self._publish(camera_id, "stopped", moment, zones=feedback_zones)
        if self.tracker.idle(camera_id):
            self.tracker.forget(camera_id)

    def _publish(
        self,
        camera_id: str,
        status: str,
        moment: Moment,
        detections: list[dict[str, Any]] | None = None,
        zones: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        payload = self._feedback_payload(camera_id, status, detections, zones, error, moment.utc)
        with self._feedback_lock:
            self._feedback[camera_id] = payload

    @staticmethod
    def _feedback_payload(
        camera_id: str,
        status: str,
        detections: list[dict[str, Any]] | None = None,
        zones: list[dict[str, Any]] | None = None,
        error: str | None = None,
        updated_at: datetime | None = None,
    ) -> dict[str, Any]:
        return {
            "camera_id": camera_id,
            "status": status,
            "updated_at": updated_at.isoformat() if updated_at else None,
            "detections": detections or [],
            "zones": zones or [],
            "error": error,
        }
