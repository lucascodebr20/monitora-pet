from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.infra.media.pet_image_store import PetImageStore
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.infra.repositories.pet_repository import PetRepository


@dataclass(frozen=True)
class PetMatch:
    pet_id: str
    confidence: float
    method: str = "appearance-histogram-v1"


@dataclass(frozen=True)
class PetAnalysis:
    match: PetMatch | None
    decision: str
    scores: tuple[dict, ...]
    minimum_similarity: float
    minimum_margin: float


class PetIdentifier:
    """Identifies cats locally from profile and human-confirmed reference images."""

    MINIMUM_SIMILARITY = PetIdentificationRepository.DEFAULT_MINIMUM_SIMILARITY
    MINIMUM_MARGIN = PetIdentificationRepository.DEFAULT_MINIMUM_MARGIN
    MAX_REFERENCES_PER_PET = 8
    CALIBRATION_INTERVAL = 10

    def __init__(
        self,
        repository: PetRepository,
        image_store: PetImageStore,
        analysis_repository: PetIdentificationRepository | None = None,
    ) -> None:
        self.repository = repository
        self.image_store = image_store
        self.analysis_repository = analysis_repository

    def identify(self, capture_path: str | None, species: str) -> PetMatch | None:
        return self.analyze(capture_path, species).match

    def analyze(self, capture_path: str | None, species: str) -> PetAnalysis:
        calibration = self.analysis_repository.current_calibration() if self.analysis_repository else {
            "minimum_similarity": self.MINIMUM_SIMILARITY,
            "minimum_margin": self.MINIMUM_MARGIN,
        }
        minimum_similarity = float(calibration["minimum_similarity"])
        minimum_margin = float(calibration["minimum_margin"])
        if not capture_path or species != "CAT":
            return PetAnalysis(None, "UNSUPPORTED", (), minimum_similarity, minimum_margin)
        try:
            capture = self._read(self.image_store.resolve(capture_path))
        except (OSError, ValueError):
            return PetAnalysis(None, "CAPTURE_UNAVAILABLE", (), minimum_similarity, minimum_margin)
        if capture is None:
            return PetAnalysis(None, "CAPTURE_UNAVAILABLE", (), minimum_similarity, minimum_margin)
        try:
            capture_descriptor = self._descriptor(capture)
        except cv2.error:
            return PetAnalysis(None, "CAPTURE_UNAVAILABLE", (), minimum_similarity, minimum_margin)
        candidates: list[dict] = []
        for pet in self.repository.list_by_species(species):
            paths = self._reference_paths(pet)
            similarities = [
                self._similarity(capture_descriptor, descriptor)
                for path in paths
                if (descriptor := self._descriptor_for_path(path)) is not None
            ]
            if similarities:
                candidates.append({
                    "pet_id": str(pet["id"]),
                    "confidence": round(max(similarities), 4),
                    "reference_count": len(similarities),
                })
        if not candidates:
            return PetAnalysis(None, "NO_REFERENCES", (), minimum_similarity, minimum_margin)
        candidates.sort(key=lambda item: item["confidence"], reverse=True)
        best = candidates[0]
        runner_up = candidates[1]["confidence"] if len(candidates) > 1 else 0.0
        if best["confidence"] < minimum_similarity:
            decision = "LOW_SIMILARITY"
            match = None
        elif best["confidence"] - runner_up < minimum_margin:
            decision = "AMBIGUOUS"
            match = None
        else:
            decision = "MATCHED"
            match = PetMatch(best["pet_id"], best["confidence"])
        return PetAnalysis(match, decision, tuple(candidates), minimum_similarity, minimum_margin)

    def record_analysis(
        self,
        event_id: str,
        capture_path: str | None,
        species: str,
        analysis: PetAnalysis,
    ) -> None:
        if not self.analysis_repository:
            return
        self.analysis_repository.create_analysis(
            event_id, species, capture_path, analysis.decision,
            analysis.match.pet_id if analysis.match else None,
            analysis.match.confidence if analysis.match else None,
            analysis.minimum_similarity, analysis.minimum_margin, list(analysis.scores),
        )

    def learn_from_review(self, event_id: str, pet_id: str) -> None:
        if not self.analysis_repository or not self.analysis_repository.mark_review(event_id, pet_id):
            return
        reviewed_count = self.analysis_repository.reviewed_count()
        current = self.analysis_repository.current_calibration()
        if reviewed_count - int(current["interaction_count"]) < self.CALIBRATION_INTERVAL:
            return
        samples = self.analysis_repository.reviewed_samples()
        positive_scores: list[float] = []
        correct_margins: list[float] = []
        correct = 0
        for sample in samples:
            scores = {score["pet_id"]: float(score["confidence"]) for score in sample["scores"]}
            actual_score = scores.get(sample["reviewed_pet_id"])
            if actual_score is None:
                continue
            competitors = [score for candidate_id, score in scores.items() if candidate_id != sample["reviewed_pet_id"]]
            positive_scores.append(actual_score)
            correct_margins.append(actual_score - max(competitors, default=0.0))
            correct += int(sample["selected_pet_id"] == sample["reviewed_pet_id"])
        if not positive_scores:
            return
        minimum_similarity = float(np.clip(np.percentile(positive_scores, 20), 0.60, 0.90))
        positive_margins = [margin for margin in correct_margins if margin > 0]
        minimum_margin = float(np.clip(
            np.percentile(positive_margins, 20) if positive_margins else self.MINIMUM_MARGIN,
            0.03,
            0.20,
        ))
        self.analysis_repository.create_calibration(
            round(minimum_similarity, 4), round(minimum_margin, 4), reviewed_count,
            round(correct / len(samples), 4),
        )

    def logs(self, limit: int = 100) -> dict:
        if not self.analysis_repository:
            return {"analyses": [], "calibration": None, "interactions_until_calibration": self.CALIBRATION_INTERVAL}
        calibration = self.analysis_repository.current_calibration()
        reviewed_count = self.analysis_repository.reviewed_count()
        progress = reviewed_count - int(calibration["interaction_count"])
        return {
            "analyses": self.analysis_repository.list_analyses(limit),
            "calibration": calibration,
            "interactions_until_calibration": max(0, self.CALIBRATION_INTERVAL - progress),
        }

    def _reference_paths(self, pet: dict) -> list[str]:
        paths: list[str] = []
        if pet.get("photo_path"):
            paths.append(str(pet["photo_path"]))
        paths.extend(
            str(reference["image_path"])
            for reference in self.repository.list_reference_images(str(pet["id"]))[:self.MAX_REFERENCES_PER_PET]
        )
        return paths

    def _descriptor_for_path(self, relative_path: str) -> tuple[np.ndarray, np.ndarray] | None:
        try:
            image = self._read(self.image_store.resolve(relative_path))
            return self._descriptor(image) if image is not None else None
        except (cv2.error, OSError, ValueError):
            return None

    @staticmethod
    def _read(path: Path):
        return cv2.imread(str(path), cv2.IMREAD_COLOR) if path.is_file() else None

    @staticmethod
    def _descriptor(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        resized = cv2.resize(image, (160, 160), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        histogram = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
        histogram = cv2.normalize(histogram, None, alpha=1, norm_type=cv2.NORM_L1).flatten()
        lab = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB).astype(np.float32) / 255.0
        statistics = np.concatenate((lab.mean(axis=(0, 1)), lab.std(axis=(0, 1))))
        return histogram, statistics

    @staticmethod
    def _similarity(
        first: tuple[np.ndarray, np.ndarray],
        second: tuple[np.ndarray, np.ndarray],
    ) -> float:
        histogram_similarity = 1.0 - cv2.compareHist(first[0], second[0], cv2.HISTCMP_BHATTACHARYYA)
        statistics_distance = float(np.linalg.norm(first[1] - second[1]) / np.sqrt(len(first[1])))
        statistics_similarity = max(0.0, 1.0 - statistics_distance)
        return float(np.clip(histogram_similarity * 0.8 + statistics_similarity * 0.2, 0.0, 1.0))
