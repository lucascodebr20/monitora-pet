from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain.detection import Detection
from app.domain.enums import PetSpecies
from app.domain.geometry import point_in_polygon, polygon_rectangle_overlap_ratio
from app.domain.zone_presence import PresenceState, TransitionType, ZonePresenceMachine
from app.infra.ai.yolox_detector import YoloXDetector
from app.infra.ai.pet_identifier import PetIdentifier
from app.infra.camera.manager import CameraManager
from app.infra.media.clip_store import ClipStore
from app.infra.media.pet_image_store import PetImageStore
from app.infra.media.snapshot_store import SnapshotStore
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.zone_repository import ZoneRepository


MINIMUM_ZONE_OVERLAP = 0.2
CLIP_FPS = 3.0
MAX_CLIP_SECONDS = 300
MAX_CLIP_FRAMES = round(CLIP_FPS * MAX_CLIP_SECONDS)


@dataclass
class ZoneRuntime:
    machine: ZonePresenceMachine = field(default_factory=ZonePresenceMachine)
    event_id: str | None = None
    clip_frames: list[bytes] = field(default_factory=list)
    clip_path: str | None = None
    clip_started_at: float | None = None
    species: PetSpecies = PetSpecies.CAT


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
        self.event_repository = event_repository
        self.snapshot_store = snapshot_store
        self.clip_store = clip_store
        self.pet_image_store = pet_image_store
        self.pet_identifier = pet_identifier
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
        stopped_at = datetime.now(timezone.utc)
        for runtime in self._runtimes.values():
            self._finalize_clip(runtime, stopped_at)
        self.event_repository.finish_open_events(stopped_at.isoformat())

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
            feedback_zones = self._process_zones(camera_id, frame, zones, detections)
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
        frame,
        zones: list[dict[str, Any]],
        detections: list[Detection],
    ) -> list[dict[str, Any]]:
        now_monotonic = time.monotonic()
        now_utc = datetime.now(timezone.utc)
        feedback: list[dict[str, Any]] = []
        active_zone_ids = {zone["id"] for zone in zones}
        polygons = {
            zone["id"]: [(float(point["x"]), float(point["y"])) for point in zone["polygon"]]
            for zone in zones
        }
        detections_by_zone = self._assign_detections(polygons, detections)
        for zone_id in list(self._runtimes):
            if zone_id not in active_zone_ids and self._runtimes[zone_id].event_id is None:
                self._runtimes.pop(zone_id, None)
        for zone in zones:
            inside_detections = detections_by_zone[zone["id"]]
            confidence = max((item.confidence for item in inside_detections), default=0.0)
            runtime = self._runtimes.setdefault(zone["id"], ZoneRuntime())
            if runtime.machine.state == PresenceState.OUTSIDE and inside_detections:
                runtime.clip_frames.clear()
                runtime.clip_path = None
                runtime.clip_started_at = now_monotonic
            clip_elapsed = now_monotonic - runtime.clip_started_at if runtime.clip_started_at is not None else 0
            if inside_detections and runtime.clip_path is None and clip_elapsed <= MAX_CLIP_SECONDS and len(runtime.clip_frames) < MAX_CLIP_FRAMES:
                encoded_frame = self.clip_store.encode(frame)
                if encoded_frame:
                    runtime.clip_frames.append(encoded_frame)
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
                    primary_detection = max(inside_detections, key=lambda item: item.confidence)
                    runtime.species = primary_detection.species
                    snapshot_path = self.snapshot_store.save(
                        self.camera_manager.snapshot(camera_id), now_utc
                    )
                    pet_capture_path = self.pet_image_store.save_capture(frame, primary_detection) if self.pet_image_store else None
                    pet_analysis = self.pet_identifier.analyze(pet_capture_path, runtime.species.value) if self.pet_identifier else None
                    pet_match = pet_analysis.match if pet_analysis else None
                    started_at = now_utc - timedelta(seconds=transition.elapsed_seconds)
                    runtime.event_id = self.event_repository.create_detected_event(
                        camera_id,
                        zone["id"],
                        started_at.isoformat(),
                        now_utc.isoformat(),
                        transition.confidence,
                        snapshot_path,
                        runtime.species.value,
                        pet_capture_path,
                        pet_match.pet_id if pet_match else None,
                        pet_match.confidence if pet_match else None,
                        pet_match.method if pet_match else None,
                    )
                    if self.pet_identifier and pet_analysis:
                        self.pet_identifier.record_analysis(
                            runtime.event_id, pet_capture_path, runtime.species.value, pet_analysis
                        )
                elif transition.type == TransitionType.FINISH and runtime.event_id:
                    self._finalize_clip(runtime, now_utc)
                    ended_at = now_utc - timedelta(seconds=transition.seconds_since_seen)
                    self.event_repository.finish_detected_event(
                        runtime.event_id,
                        ended_at.isoformat(),
                        transition.elapsed_seconds,
                        "CAT_LEFT_ZONE",
                    )
                    runtime.event_id = None
                    runtime.clip_frames.clear()
                    runtime.clip_path = None
                    runtime.clip_started_at = None
            if runtime.event_id and (clip_elapsed >= MAX_CLIP_SECONDS or len(runtime.clip_frames) >= MAX_CLIP_FRAMES):
                self._finalize_clip(runtime, now_utc)
            if runtime.machine.state == PresenceState.OUTSIDE and runtime.event_id is None:
                runtime.clip_frames.clear()
                runtime.clip_path = None
                runtime.clip_started_at = None
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

    def _finalize_clip(self, runtime: ZoneRuntime, captured_at: datetime) -> None:
        if not runtime.event_id or runtime.clip_path or len(runtime.clip_frames) < 2:
            return
        clip_path = self.clip_store.save(runtime.clip_frames, captured_at, CLIP_FPS)
        if clip_path:
            self.event_repository.attach_clip(runtime.event_id, clip_path)
            runtime.clip_path = clip_path
            runtime.clip_frames.clear()

    @staticmethod
    def _detection_in_zone(detection: Detection, polygon: list[tuple[float, float]]) -> bool:
        return MonitoringService._detection_zone_score(detection, polygon) >= MINIMUM_ZONE_OVERLAP

    @staticmethod
    def _detection_zone_score(detection: Detection, polygon: list[tuple[float, float]]) -> float:
        rectangle = detection.x1, detection.y1, detection.x2, detection.y2
        overlap = polygon_rectangle_overlap_ratio(polygon, rectangle)
        if point_in_polygon(detection.centroid, polygon):
            return max(1.0, overlap)
        return overlap

    @staticmethod
    def _assign_detections(
        polygons: dict[str, list[tuple[float, float]]],
        detections: list[Detection],
    ) -> dict[str, list[Detection]]:
        assigned = {zone_id: [] for zone_id in polygons}
        for detection in detections:
            candidates: list[tuple[float, float, str]] = []
            for zone_id, polygon in polygons.items():
                score = MonitoringService._detection_zone_score(detection, polygon)
                if score < MINIMUM_ZONE_OVERLAP:
                    continue
                center_x = sum(point[0] for point in polygon) / len(polygon)
                center_y = sum(point[1] for point in polygon) / len(polygon)
                distance = (detection.centroid[0] - center_x) ** 2 + (detection.centroid[1] - center_y) ** 2
                candidates.append((score, -distance, zone_id))
            if candidates:
                assigned[max(candidates)[2]].append(detection)
        return assigned
