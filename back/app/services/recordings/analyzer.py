from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import numpy as np

from app.domain.clock import Moment
from app.domain.detection import Detection
from app.domain.intervals import contains, subtract_intervals
from app.infra.ai.motion_gate import MotionGate
from app.infra.ai.pet_identifier import PetIdentifier
from app.services.event.auto_review import AutoReviewService
from app.infra.media.clip_store import ClipStore
from app.infra.media.pet_image_store import PetImageStore
from app.infra.media.recording_reader import RecordingReader
from app.infra.media.snapshot_store import SnapshotStore
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.monitoring_session_repository import MonitoringSessionRepository
from app.infra.repositories.recording_repository import RecordingRepository
from app.infra.repositories.zone_repository import ZoneRepository
from app.services.event.purge import EventPurgeService
from app.services.monitoring.analysis import Detector, FrameAnalyzer
from app.services.monitoring.clips import ClipRecorder
from app.services.monitoring.events import EventRecorder
from app.services.monitoring.snapshots import FrameSnapshotSource
from app.services.monitoring.tracking import ZoneTracker

logger = logging.getLogger(__name__)

SAMPLE_FPS = 2.0
PROGRESS_INTERVAL_SECONDS = 5.0
SOURCE_RECORDING = "RECORDING"
END_REASON_IMPORT_FAILED = "IMPORT_FAILED"
END_REASON_IMPORT_INTERRUPTED = "IMPORT_INTERRUPTED"


class ImportInterrupted(RuntimeError):
    pass


@dataclass
class RecordingBatchResult:
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    frames_analyzed: int = 0
    detections_run: int = 0
    interrupted: bool = False
    failures: dict[str, str] = field(default_factory=dict)


def moment_at(instant: datetime) -> Moment:
    return Moment(instant.timestamp(), instant)


class RecordingAnalyzer:
    def __init__(
        self,
        detector: Detector,
        zone_repository: ZoneRepository,
        event_repository: EventRepository,
        snapshot_store: SnapshotStore,
        clip_store: ClipStore,
        session_repository: MonitoringSessionRepository,
        recording_repository: RecordingRepository,
        purge: EventPurgeService,
        pet_image_store: PetImageStore | None = None,
        pet_identifier: PetIdentifier | None = None,
        auto_review: AutoReviewService | None = None,
        reader_factory: Callable[[Path], Any] = RecordingReader,
        motion_gate_factory: Callable[[], Any] = MotionGate,
        sample_fps: float = SAMPLE_FPS,
    ) -> None:
        self.detector = detector
        self.zone_repository = zone_repository
        self.event_repository = event_repository
        self.snapshot_store = snapshot_store
        self.clip_store = clip_store
        self.session_repository = session_repository
        self.recording_repository = recording_repository
        self.purge = purge
        self.pet_image_store = pet_image_store
        self.pet_identifier = pet_identifier
        self.auto_review = auto_review
        self.reader_factory = reader_factory
        self.motion_gate_factory = motion_gate_factory
        self.sample_fps = sample_fps

    def analyze_camera(
        self,
        camera_id: str,
        recordings: list[dict[str, Any]],
        should_stop: Callable[[], bool] | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> RecordingBatchResult:
        result = RecordingBatchResult()
        events = EventRecorder(
            self.event_repository,
            self.snapshot_store,
            FrameSnapshotSource(self.snapshot_store),
            self.pet_image_store,
            self.pet_identifier,
            source=SOURCE_RECORDING,
            auto_review=self.auto_review,
        )
        tracker = ZoneTracker(ClipRecorder(self.clip_store, self.event_repository), events, self.pet_image_store)
        analyzer = FrameAnalyzer(self.detector, self.zone_repository, tracker)
        settle_seconds = self._settle_seconds(camera_id)
        last_time: datetime | None = None
        for recording in sorted(recordings, key=lambda item: (item["started_at"], item["created_at"])):
            if should_stop and should_stop():
                result.interrupted = True
                break
            start = datetime.fromisoformat(recording["started_at"])
            end = datetime.fromisoformat(recording["ended_at"])
            windows = subtract_intervals(start, end, self.session_repository.covered_intervals(camera_id, start, end))
            if not windows:
                self.recording_repository.set_status(recording["id"], "SKIPPED")
                result.skipped += 1
                continue
            self.recording_repository.set_status(recording["id"], "PROCESSING")
            events.recording_id = recording["id"]
            if last_time is not None and start > last_time:
                self._settle(analyzer, camera_id, start)
            try:
                self._analyze_recording(analyzer, camera_id, recording, start, windows, result, should_stop, on_progress)
            except ImportInterrupted:
                self._settle(analyzer, camera_id, end)
                self.purge.purge_recording(recording["id"])
                self.recording_repository.reset(recording["id"])
                result.interrupted = True
                break
            except Exception as error:
                logger.exception("Falha ao analisar a gravação %s", recording["path"])
                self._settle(analyzer, camera_id, end)
                self.event_repository.finish_open_recording_events(
                    recording["id"], end.isoformat(), END_REASON_IMPORT_FAILED
                )
                self.recording_repository.set_status(recording["id"], "FAILED", str(error))
                result.failed += 1
                result.failures[recording["id"]] = str(error)
            else:
                self.recording_repository.set_status(recording["id"], "DONE")
                result.processed += 1
            last_time = end
        if last_time is not None:
            self._settle(analyzer, camera_id, last_time + timedelta(seconds=settle_seconds))
            tracker.finalize_clips(last_time)
        return result

    def _analyze_recording(
        self,
        analyzer: FrameAnalyzer,
        camera_id: str,
        recording: dict[str, Any],
        start: datetime,
        windows: list[tuple[datetime, datetime]],
        result: RecordingBatchResult,
        should_stop: Callable[[], bool] | None,
        on_progress: Callable[[str, float], None] | None,
    ) -> None:
        reader = self.reader_factory(Path(recording["path"]))
        gate = self.motion_gate_factory()
        cached: list[Detection] | None = None
        inside_window = False
        last_progress = 0.0
        for offset, frame in reader.frames(self.sample_fps):
            if should_stop and should_stop():
                raise ImportInterrupted()
            instant = start + timedelta(seconds=offset)
            if not contains(windows, instant):
                if inside_window:
                    self._settle(analyzer, camera_id, instant)
                inside_window = False
                cached = None
                continue
            inside_window = True
            moment = moment_at(instant)
            moved = gate.changed(frame)
            if cached is None or moved:
                cached = analyzer.analyze(camera_id, frame, moment).detections
                result.detections_run += 1
            else:
                analyzer.track(camera_id, frame, cached, moment)
            result.frames_analyzed += 1
            if offset - last_progress >= PROGRESS_INTERVAL_SECONDS:
                last_progress = offset
                self.recording_repository.update_progress(recording["id"], offset)
                if on_progress:
                    on_progress(recording["id"], offset)

    def _settle(self, analyzer: FrameAnalyzer, camera_id: str, instant: datetime) -> None:
        moment = moment_at(instant)
        analyzer.absence(camera_id, moment)
        analyzer.absence(camera_id, moment)

    def _settle_seconds(self, camera_id: str) -> float:
        zones = self.zone_repository.list(camera_id)
        cooldown = max((float(zone["cooldown_seconds"]) for zone in zones), default=0.0)
        tolerance = max((float(zone["absence_tolerance_seconds"]) for zone in zones), default=0.0)
        return cooldown + tolerance + 1.0
