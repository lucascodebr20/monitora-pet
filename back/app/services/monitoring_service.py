from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain.detection import Detection
from app.domain.geometry import point_in_polygon
from app.domain.zone_presence import PresenceState, TransitionType, ZonePresenceMachine
from app.infra.ai.yolox_detector import YoloXDetector
from app.infra.camera.manager import CameraManager
from app.infra.media.snapshot_store import SnapshotStore
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.zone_repository import ZoneRepository


@dataclass
class ZoneRuntime:
    machine: ZonePresenceMachine = field(default_factory=ZonePresenceMachine)
    event_id: str | None = None


class MonitoringService:
    def __init__(
        self,
        camera_manager: CameraManager,
        zone_repository: ZoneRepository,
        event_repository: EventRepository,
        snapshot_store: SnapshotStore,
        detector: YoloXDetector | None,
        model_error: str | None = None,
    ) -> None:
        self.camera_manager = camera_manager
        self.zone_repository = zone_repository
        self.event_repository = event_repository
        self.snapshot_store = snapshot_store
        self.detector = detector
        self.model_error = model_error
        self._runtimes: dict[str, ZoneRuntime] = {}
        self._feedback: dict[str, dict[str, Any]] = {}
        self._feedback_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_error: str | None = model_error

    def start(self) -> None:
        self.event_repository.finish_open_events(datetime.now(timezone.utc).isoformat())
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

    def health(self) -> dict[str, Any]:
        if self.detector is None:
            return {"status": "model_missing", "provider": "opencv-yolox-tiny", "error": self._last_error}
        return {
            "status": "running" if self._thread and self._thread.is_alive() else "stopped",
            "provider": "opencv-yolox-tiny",
            "error": self._last_error,
        }

    def feedback(self, camera_id: str) -> dict[str, Any]:
        with self._feedback_lock:
            current = self._feedback.get(camera_id)
            if current:
                return current
        return {
            "camera_id": camera_id,
            "status": self.health()["status"],
            "updated_at": None,
            "detections": [],
            "zones": [],
            "error": self._last_error,
        }

    def _run(self) -> None:
        while not self._stop.wait(0.35):
            for camera_id in self.camera_manager.connected_ids():
                if self._stop.is_set():
                    return
                self._process_camera(camera_id)

    def _process_camera(self, camera_id: str) -> None:
        frame = self.camera_manager.latest_frame(camera_id)
        if frame is None or self.detector is None:
            return
        try:
            detections = self.detector.detect(frame)
            self._last_error = None
            zones = self.zone_repository.list(camera_id)
            feedback_zones = self._process_zones(camera_id, zones, detections)
            feedback = {
                "camera_id": camera_id,
                "status": "running",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "detections": [detection.as_dict() for detection in detections],
                "zones": feedback_zones,
                "error": None,
            }
            with self._feedback_lock:
                self._feedback[camera_id] = feedback
        except Exception as error:
            self._last_error = str(error)
            with self._feedback_lock:
                self._feedback[camera_id] = {
                    "camera_id": camera_id,
                    "status": "error",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "detections": [],
                    "zones": [],
                    "error": str(error),
                }

    def _process_zones(
        self,
        camera_id: str,
        zones: list[dict[str, Any]],
        detections: list[Detection],
    ) -> list[dict[str, Any]]:
        now_monotonic = time.monotonic()
        now_utc = datetime.now(timezone.utc)
        feedback: list[dict[str, Any]] = []
        active_zone_ids = {zone["id"] for zone in zones}
        for zone_id in list(self._runtimes):
            if zone_id not in active_zone_ids and self._runtimes[zone_id].event_id is None:
                self._runtimes.pop(zone_id, None)
        for zone in zones:
            polygon = [(float(point["x"]), float(point["y"])) for point in zone["polygon"]]
            inside_detections = [
                detection for detection in detections if point_in_polygon(detection.centroid, polygon)
            ]
            confidence = max((item.confidence for item in inside_detections), default=0.0)
            runtime = self._runtimes.setdefault(zone["id"], ZoneRuntime())
            transitions = runtime.machine.observe(
                bool(inside_detections),
                confidence,
                now_monotonic,
                float(zone["minimum_presence_seconds"]),
                float(zone["absence_tolerance_seconds"]),
                float(zone["cooldown_seconds"]),
            )
            for transition in transitions:
                if transition.type == TransitionType.CONFIRM:
                    snapshot_path = self.snapshot_store.save(
                        self.camera_manager.snapshot(camera_id), now_utc
                    )
                    started_at = now_utc - timedelta(seconds=transition.elapsed_seconds)
                    runtime.event_id = self.event_repository.create_detected_event(
                        camera_id,
                        zone["id"],
                        started_at.isoformat(),
                        now_utc.isoformat(),
                        transition.confidence,
                        snapshot_path,
                    )
                elif transition.type == TransitionType.FINISH and runtime.event_id:
                    ended_at = now_utc - timedelta(seconds=transition.seconds_since_seen)
                    self.event_repository.finish_detected_event(
                        runtime.event_id,
                        ended_at.isoformat(),
                        transition.elapsed_seconds,
                        "CAT_LEFT_ZONE",
                    )
                    runtime.event_id = None
            elapsed = runtime.machine.elapsed(now_monotonic)
            minimum = float(zone["minimum_presence_seconds"])
            feedback.append({
                "zone_id": zone["id"],
                "state": runtime.machine.state,
                "inside": bool(inside_detections),
                "elapsed_seconds": elapsed,
                "progress": min(1.0, elapsed / minimum) if minimum else 1.0,
                "confidence": confidence,
                "event_id": runtime.event_id,
            })
        return feedback
