from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from app.domain.clock import Moment
from app.domain.detection import Detection
from app.infra.repositories.zone_repository import ZoneRepository
from app.services.monitoring.tracking import ZoneTracker


class Detector(Protocol):
    def detect(self, frame: np.ndarray) -> list[Detection]: ...


@dataclass(frozen=True)
class FrameAnalysis:
    detections: list[Detection]
    zones: list[dict[str, Any]]


class FrameAnalyzer:
    def __init__(self, detector: Detector, zone_repository: ZoneRepository, tracker: ZoneTracker) -> None:
        self.detector = detector
        self.zone_repository = zone_repository
        self.tracker = tracker

    def analyze(self, camera_id: str, frame: np.ndarray, moment: Moment) -> FrameAnalysis:
        return self.track(camera_id, frame, self.detector.detect(frame), moment)

    def track(self, camera_id: str, frame: np.ndarray, detections: list[Detection], moment: Moment) -> FrameAnalysis:
        zones = self.zone_repository.list(camera_id)
        return FrameAnalysis(detections, self.tracker.track(camera_id, frame, zones, detections, moment))

    def absence(self, camera_id: str, moment: Moment) -> list[dict[str, Any]]:
        zones = self.zone_repository.list(camera_id)
        return self.tracker.track(camera_id, None, zones, [], moment)
