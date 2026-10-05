from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

import numpy as np

from app.domain.detection import Detection
from app.domain.enums import PetSpecies
from app.domain.zone_matching import assign_detections
from app.domain.zone_presence import PresenceState, TransitionType, ZonePresenceMachine
from app.infra.media.pet_image_store import PetImageStore
from app.services.monitoring.clips import ClipBuffer, ClipRecorder
from app.services.monitoring.events import EventRecorder

MAX_PET_OBSERVATIONS = 5


@dataclass
class ZoneRuntime:
    machine: ZonePresenceMachine = field(default_factory=ZonePresenceMachine)
    clip: ClipBuffer = field(default_factory=ClipBuffer)
    species: PetSpecies = PetSpecies.CAT
    observations: list[np.ndarray] = field(default_factory=list)

    @property
    def event_id(self) -> str | None:
        return self.clip.event_id

    def clear(self) -> None:
        self.clip.reset()
        self.observations.clear()

    def idle(self) -> bool:
        return self.machine.state == PresenceState.OUTSIDE and self.event_id is None


class ZoneTracker:
    def __init__(self, clips: ClipRecorder, events: EventRecorder, pet_image_store: PetImageStore | None = None) -> None:
        self.clips = clips
        self.events = events
        self.pet_image_store = pet_image_store
        self.runtimes: dict[str, dict[str, ZoneRuntime]] = {}

    def track(
        self,
        camera_id: str,
        frame: np.ndarray | None,
        zones: list[dict[str, Any]],
        detections: list[Detection],
    ) -> list[dict[str, Any]]:
        now = time.monotonic()
        now_utc = datetime.now(timezone.utc)
        runtimes = self.runtimes.setdefault(camera_id, {})
        polygons = {
            zone["id"]: [(float(point["x"]), float(point["y"])) for point in zone["polygon"]]
            for zone in zones
        }
        by_zone = assign_detections(polygons, detections)
        for zone_id in list(runtimes):
            if zone_id not in polygons and runtimes[zone_id].event_id is None:
                runtimes.pop(zone_id)
        return [
            self._track_zone(camera_id, zone, runtimes.setdefault(zone["id"], ZoneRuntime()), frame, by_zone[zone["id"]], now, now_utc)
            for zone in zones
        ]

    def has_state(self, camera_id: str) -> bool:
        return bool(self.runtimes.get(camera_id))

    def idle(self, camera_id: str) -> bool:
        return all(runtime.idle() for runtime in self.runtimes.get(camera_id, {}).values())

    def forget(self, camera_id: str) -> None:
        self.runtimes.pop(camera_id, None)

    def buffers(self) -> Iterator[ClipBuffer]:
        for camera_runtimes in self.runtimes.values():
            for runtime in camera_runtimes.values():
                yield runtime.clip

    def clip_bytes(self) -> int:
        return self.clips.total_bytes(self.buffers())

    def finalize_clips(self, now_utc: datetime) -> None:
        for buffer in list(self.buffers()):
            self.clips.finalize(buffer, now_utc)

    def _track_zone(
        self,
        camera_id: str,
        zone: dict[str, Any],
        runtime: ZoneRuntime,
        frame: np.ndarray | None,
        inside: list[Detection],
        now: float,
        now_utc: datetime,
    ) -> dict[str, Any]:
        confidence = max((detection.confidence for detection in inside), default=0.0)
        if runtime.machine.state == PresenceState.OUTSIDE and inside:
            runtime.clip.reset(started_at=now)
        if inside and frame is not None:
            self.clips.capture(runtime.clip, frame, now, now_utc, self.buffers())
            self._observe_pet(runtime, frame, inside)
        transitions = runtime.machine.observe(
            bool(inside),
            confidence,
            now,
            float(zone["minimum_presence_seconds"]),
            float(zone["absence_tolerance_seconds"]),
            float(zone["cooldown_seconds"]),
        )
        for transition in transitions:
            if transition.type == TransitionType.CONFIRM and frame is not None:
                primary = max(inside, key=lambda detection: detection.confidence)
                runtime.species = primary.species
                runtime.clip.event_id = self.events.open(
                    camera_id, zone["id"], runtime.species, transition, runtime.observations, frame, primary, now_utc
                )
            elif transition.type == TransitionType.FINISH and runtime.event_id:
                self.clips.finalize(runtime.clip, now_utc)
                self.events.close(runtime.event_id, transition, now_utc)
                runtime.clear()
        if runtime.event_id and runtime.clip.exhausted(now):
            self.clips.finalize(runtime.clip, now_utc)
        if runtime.idle():
            runtime.clear()
        elapsed = runtime.machine.elapsed(now)
        minimum = float(zone["minimum_presence_seconds"])
        return {
            "zone_id": zone["id"],
            "state": runtime.machine.state,
            "inside": bool(inside),
            "elapsed_seconds": elapsed,
            "progress": min(1.0, elapsed / minimum) if minimum else 1.0,
            "confidence": confidence,
            "event_id": runtime.event_id,
        }

    def _observe_pet(self, runtime: ZoneRuntime, frame: np.ndarray, inside: list[Detection]) -> None:
        if not self.pet_image_store:
            return
        primary = max(inside, key=lambda detection: detection.confidence)
        crop = self.pet_image_store.extract_capture(frame, primary)
        if crop is not None:
            runtime.observations.append(crop)
            del runtime.observations[:-MAX_PET_OBSERVATIONS]
