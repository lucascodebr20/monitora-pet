from __future__ import annotations

from datetime import datetime, timedelta
from dataclasses import asdict

import numpy as np

from app.domain.detection import Detection
from app.domain.enums import PetSpecies
from app.domain.zone_presence import PresenceTransition
from app.infra.ai.pet_identifier import PetAnalysis, PetIdentifier
from app.infra.media.pet_image_store import PetImageStore
from app.infra.media.snapshot_store import SnapshotStore
from app.infra.repositories.event_repository import EventRepository
from app.services.event.auto_review import AutoReviewService
from app.services.monitoring.snapshots import SnapshotSource

END_REASON_LEFT_ZONE = "PET_LEFT_ZONE"


class EventRecorder:
    def __init__(
        self,
        event_repository: EventRepository,
        snapshot_store: SnapshotStore,
        snapshot_source: SnapshotSource,
        pet_image_store: PetImageStore | None = None,
        pet_identifier: PetIdentifier | None = None,
        source: str = "LIVE",
        auto_review: AutoReviewService | None = None,
    ) -> None:
        self.event_repository = event_repository
        self.snapshot_store = snapshot_store
        self.snapshot_source = snapshot_source
        self.pet_image_store = pet_image_store
        self.pet_identifier = pet_identifier
        self.source = source
        self.auto_review = auto_review
        self.recording_id: str | None = None

    def open(
        self,
        camera_id: str,
        zone_id: str,
        species: PetSpecies,
        transition: PresenceTransition,
        observations: list[np.ndarray],
        frame: np.ndarray,
        primary: Detection,
        now_utc: datetime,
        ambiguity: str | None = None,
    ) -> str:
        snapshot_path = self.snapshot_store.save(self.snapshot_source.snapshot(camera_id, frame), now_utc)
        capture_path = self._capture(observations, frame, primary, now_utc)
        analysis = self._analyze(observations, capture_path, species)
        if analysis and ambiguity:
            analysis = self._ambiguous(analysis, ambiguity)
        match = analysis.match if analysis else None
        started_at = now_utc - timedelta(seconds=transition.elapsed_seconds)
        event_id = self.event_repository.create_detected_event(
            camera_id,
            zone_id,
            started_at.isoformat(),
            now_utc.isoformat(),
            transition.confidence,
            snapshot_path,
            species.value,
            capture_path,
            match.pet_id if match else None,
            match.confidence if match else None,
            match.method if match else None,
            source=self.source,
            recording_id=self.recording_id,
        )
        if self.pet_identifier and analysis:
            self.pet_identifier.record_analysis(event_id, capture_path, species.value, analysis, len(observations), "OPEN")
        return event_id

    def _maybe_auto_review(self, event_id: str, species: PetSpecies, analysis: PetAnalysis | None) -> None:
        if not self.auto_review or not analysis or not analysis.match:
            return
        scores = sorted((candidate["confidence"] for candidate in analysis.scores), reverse=True)
        runner_up = scores[1] if len(scores) > 1 else 0.0
        margin = analysis.match.confidence - runner_up
        if self.auto_review.should_confirm(species.value, analysis.match.pet_id, analysis.match.confidence, margin):
            self.auto_review.confirm(event_id, analysis.match.pet_id)

    def close(self, event_id: str, transition: PresenceTransition, now_utc: datetime,
              observations: list[np.ndarray] | None = None, species: PetSpecies = PetSpecies.CAT,
              ambiguity: str | None = None) -> None:
        ended_at = now_utc - timedelta(seconds=transition.seconds_since_seen)
        analysis = self.refine(event_id, observations or [], species, now_utc, ambiguity)
        self.event_repository.finish_detected_event(
            event_id, ended_at.isoformat(), transition.elapsed_seconds, END_REASON_LEFT_ZONE
        )
        if len(observations or []) >= 3 and not ambiguity and not self.event_repository.has_review(event_id):
            self._maybe_auto_review(event_id, species, analysis)

    def refine(self, event_id: str, observations: list[np.ndarray], species: PetSpecies,
               now_utc: datetime, ambiguity: str | None = None) -> PetAnalysis | None:
        if not self.pet_identifier or self.event_repository.has_review(event_id):
            return
        event = self.event_repository.get(event_id)
        if not event:
            return
        capture_path = event.get("pet_capture_path")
        previous_path = capture_path
        analysis = self._analyze(observations, capture_path, species)
        if not analysis:
            return
        if ambiguity:
            analysis = self._ambiguous(analysis, ambiguity)
        elif observations and self.pet_image_store:
            best = max(observations, key=PetIdentifier.image_quality)
            capture_path = self.pet_image_store.save_capture_image(best, now_utc)
        updated = self.event_repository.finalize_identification(event_id, capture_path, asdict(analysis), len(observations))
        unused_path = previous_path if updated else capture_path
        if self.pet_image_store and unused_path and unused_path != (capture_path if updated else previous_path):
            if not self.event_repository.capture_is_used(unused_path):
                self.pet_image_store.resolve(unused_path).unlink(missing_ok=True)
        return analysis if updated else None

    @staticmethod
    def _ambiguous(analysis: PetAnalysis, reason: str) -> PetAnalysis:
        return PetAnalysis(None, reason, (), analysis.minimum_similarity, analysis.minimum_margin, analysis.method)

    def close_all_open(self, ended_at: datetime) -> None:
        self.event_repository.finish_open_events(ended_at.isoformat(), self.source)

    def _capture(
        self, observations: list[np.ndarray], frame: np.ndarray, primary: Detection, captured_at: datetime
    ) -> str | None:
        if not self.pet_image_store:
            return None
        if observations:
            best = max(observations, key=PetIdentifier.image_quality)
            return self.pet_image_store.save_capture_image(best, captured_at)
        return self.pet_image_store.save_capture(frame, primary, captured_at)

    def _analyze(self, observations: list[np.ndarray], capture_path: str | None, species: PetSpecies) -> PetAnalysis | None:
        if not self.pet_identifier:
            return None
        if observations:
            return self.pet_identifier.analyze_images(observations, species.value)
        return self.pet_identifier.analyze(capture_path, species.value)
