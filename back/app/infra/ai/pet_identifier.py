from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

from app.core.config import PET_EMBEDDING_MODEL_PATH
from app.infra.media.pet_image_store import PetImageStore
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.infra.repositories.pet_repository import PetRepository

Descriptor = np.ndarray | tuple[np.ndarray, np.ndarray, np.ndarray]


@dataclass(frozen=True)
class PetMatch:
    pet_id: str
    confidence: float
    method: str = "mobilenet-embedding-v2"


@dataclass(frozen=True)
class PetAnalysis:
    match: PetMatch | None
    decision: str
    scores: tuple[dict, ...]
    minimum_similarity: float
    minimum_margin: float
    method: str = "mobilenet-embedding-v2"


class PetIdentifier:
    """Identifies cats from a quality-controlled, diverse gallery of confirmed images."""

    METHOD = "mobilenet-embedding-v2"
    MINIMUM_SIMILARITY = 0.731
    MINIMUM_MARGIN = 0.064
    MAX_REFERENCES_PER_PET = 32
    CALIBRATION_INTERVAL = 10
    MINIMUM_REFERENCE_QUALITY = 0.22

    def __init__(self, repository: PetRepository, image_store: PetImageStore,
                 analysis_repository: PetIdentificationRepository | None = None) -> None:
        self.repository = repository
        self.image_store = image_store
        self.analysis_repository = analysis_repository
        self._descriptor_cache: dict[str, tuple[int, int, Descriptor, float]] = {}
        self._embedding_network = (
            cv2.dnn.readNetFromONNX(str(PET_EMBEDDING_MODEL_PATH))
            if PET_EMBEDDING_MODEL_PATH.is_file() else None
        )

    def identify(self, capture_path: str | None, species: str) -> PetMatch | None:
        return self.analyze(capture_path, species).match

    def analyze(self, capture_path: str | None, species: str) -> PetAnalysis:
        if not capture_path:
            return self._empty_analysis("UNSUPPORTED", species)
        try:
            image = self._read(self.image_store.resolve(capture_path))
        except (OSError, ValueError):
            image = None
        if image is None:
            return self._empty_analysis("CAPTURE_UNAVAILABLE", species)
        return self.analyze_images([image], species)

    def analyze_images(self, images: Iterable[np.ndarray], species: str) -> PetAnalysis:
        minimum_similarity, minimum_margin = self._thresholds()
        if species != "CAT":
            return PetAnalysis(None, "UNSUPPORTED", (), minimum_similarity, minimum_margin, self.METHOD)
        descriptors: list[Descriptor] = []
        for image in images:
            if image is None or image.size == 0:
                continue
            try:
                descriptors.append(self._descriptor(image))
            except cv2.error:
                continue
        if not descriptors:
            return PetAnalysis(None, "CAPTURE_UNAVAILABLE", (), minimum_similarity, minimum_margin, self.METHOD)

        candidates: list[dict] = []
        for pet in self.repository.list_by_species(species):
            references = self._reference_descriptors(pet)
            if not references:
                continue
            observation_scores = [self._gallery_score(descriptor, references) for descriptor in descriptors]
            candidates.append({
                "pet_id": str(pet["id"]),
                "confidence": round(float(np.median(observation_scores)), 4),
                "reference_count": len(references),
            })
        if not candidates:
            return PetAnalysis(None, "NO_REFERENCES", (), minimum_similarity, minimum_margin, self.METHOD)
        candidates.sort(key=lambda item: item["confidence"], reverse=True)
        best = candidates[0]
        runner_up = candidates[1]["confidence"] if len(candidates) > 1 else 0.0
        if best["confidence"] < minimum_similarity:
            decision, match = "LOW_SIMILARITY", None
        elif best["confidence"] - runner_up < minimum_margin:
            decision, match = "AMBIGUOUS", None
        else:
            decision = "MATCHED"
            match = PetMatch(best["pet_id"], best["confidence"], self.METHOD)
        return PetAnalysis(match, decision, tuple(candidates), minimum_similarity, minimum_margin, self.METHOD)

    def record_analysis(self, event_id: str, capture_path: str | None, species: str,
                        analysis: PetAnalysis) -> None:
        if not self.analysis_repository:
            return
        self.analysis_repository.create_analysis(
            event_id, species, capture_path, analysis.decision,
            analysis.match.pet_id if analysis.match else None,
            analysis.match.confidence if analysis.match else None,
            analysis.minimum_similarity, analysis.minimum_margin, list(analysis.scores), analysis.method,
        )

    def learn_from_review(self, event_id: str, pet_id: str) -> None:
        if not self.analysis_repository or not self.analysis_repository.mark_review(event_id, pet_id):
            return
        reviewed_count = self.analysis_repository.reviewed_count(self.METHOD)
        current = self.analysis_repository.current_calibration(self.METHOD)
        if reviewed_count - int(current["interaction_count"]) < self.CALIBRATION_INTERVAL:
            return
        samples = self.analysis_repository.reviewed_samples(self.METHOD)
        usable: list[tuple[float, float, bool]] = []
        top1_correct = 0
        for sample in samples:
            scores = sorted(
                ((score["pet_id"], float(score["confidence"])) for score in sample["scores"]),
                key=lambda item: item[1], reverse=True,
            )
            if not scores:
                continue
            is_correct = scores[0][0] == sample["reviewed_pet_id"]
            top1_correct += int(is_correct)
            usable.append((scores[0][1], scores[0][1] - (scores[1][1] if len(scores) > 1 else 0.0), is_correct))
        if not usable:
            return
        minimum_similarity, minimum_margin = self._choose_thresholds(usable)
        self.analysis_repository.create_calibration(
            minimum_similarity, minimum_margin, reviewed_count,
            round(top1_correct / len(usable), 4), self.METHOD,
        )

    def logs(self, page: int = 1, page_size: int = 10) -> dict:
        if not self.analysis_repository:
            return {"analyses": [], "total": 0, "page": page, "page_size": page_size,
                    "calibration": None,
                    "interactions_until_calibration": self.CALIBRATION_INTERVAL, "metrics": {}}
        calibration = self.analysis_repository.current_calibration(self.METHOD)
        reviewed_count = self.analysis_repository.reviewed_count(self.METHOD)
        progress = reviewed_count - int(calibration["interaction_count"])
        return {
            "analyses": self.analysis_repository.list_analyses(page_size, (page - 1) * page_size),
            "total": self.analysis_repository.count_analyses(),
            "page": page,
            "page_size": page_size,
            "calibration": calibration,
            "interactions_until_calibration": max(0, self.CALIBRATION_INTERVAL - progress),
            "metrics": self.analysis_repository.performance_metrics(self.METHOD),
            "method": self.METHOD,
        }

    def _empty_analysis(self, decision: str, species: str) -> PetAnalysis:
        minimum_similarity, minimum_margin = self._thresholds()
        return PetAnalysis(None, "UNSUPPORTED" if species != "CAT" else decision, (),
                           minimum_similarity, minimum_margin, self.METHOD)

    def _thresholds(self) -> tuple[float, float]:
        if not self.analysis_repository:
            return self.MINIMUM_SIMILARITY, self.MINIMUM_MARGIN
        calibration = self.analysis_repository.current_calibration(self.METHOD)
        if not calibration.get("created_at"):
            return self.MINIMUM_SIMILARITY, self.MINIMUM_MARGIN
        return float(calibration["minimum_similarity"]), float(calibration["minimum_margin"])

    @classmethod
    def _choose_thresholds(cls, samples: list[tuple[float, float, bool]]) -> tuple[float, float]:
        similarities = sorted({cls.MINIMUM_SIMILARITY, *(round(item[0], 3) for item in samples)})
        margins = sorted({cls.MINIMUM_MARGIN, *(round(max(0.0, item[1]), 3) for item in samples)})
        best: tuple[float, float, float, float] | None = None
        for similarity in similarities:
            for margin in margins:
                accepted = [item for item in samples if item[0] >= similarity and item[1] >= margin]
                if not accepted:
                    continue
                precision = sum(item[2] for item in accepted) / len(accepted)
                coverage = len(accepted) / len(samples)
                candidate = (coverage, precision, -similarity, -margin)
                if precision >= 0.80 and (best is None or candidate > best):
                    best = candidate
        if best is None:
            return cls.MINIMUM_SIMILARITY, cls.MINIMUM_MARGIN
        return round(-best[2], 4), round(-best[3], 4)

    def _reference_descriptors(self, pet: dict) -> list[Descriptor]:
        candidates = [item for path in self._reference_paths(pet)
                      if (item := self._descriptor_for_path(path)) is not None]
        qualified = [item for item in candidates if item[1] >= self.MINIMUM_REFERENCE_QUALITY]
        return self._select_diverse(qualified if qualified else candidates, self.MAX_REFERENCES_PER_PET)

    def _reference_paths(self, pet: dict) -> list[str]:
        paths = [str(pet["photo_path"])] if pet.get("photo_path") else []
        paths.extend(str(item["image_path"]) for item in self.repository.list_reference_images(str(pet["id"])))
        return list(dict.fromkeys(paths))

    def _descriptor_for_path(self, relative_path: str) -> tuple[Descriptor, float] | None:
        try:
            path = self.image_store.resolve(relative_path)
            stat = path.stat()
            cached = self._descriptor_cache.get(relative_path)
            if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
                return cached[2], cached[3]
            image = self._read(path)
            if image is None:
                return None
            descriptor, quality = self._descriptor(image), self.image_quality(image)
            self._descriptor_cache[relative_path] = (stat.st_mtime_ns, stat.st_size, descriptor, quality)
            return descriptor, quality
        except (cv2.error, OSError, ValueError):
            return None

    @classmethod
    def _select_diverse(cls, candidates: list[tuple[Descriptor, float]], limit: int) -> list[Descriptor]:
        if len(candidates) <= limit:
            return [descriptor for descriptor, _ in candidates]
        remaining = list(candidates)
        selected = [remaining.pop(max(range(len(remaining)), key=lambda i: remaining[i][1]))[0]]
        while remaining and len(selected) < limit:
            index = max(range(len(remaining)), key=lambda i:
                        min(1.0 - cls._similarity(remaining[i][0], item) for item in selected)
                        + remaining[i][1] * 0.08)
            selected.append(remaining.pop(index)[0])
        return selected

    @staticmethod
    def _read(path: Path):
        return cv2.imread(str(path), cv2.IMREAD_COLOR) if path.is_file() else None

    @staticmethod
    def image_quality(image: np.ndarray) -> float:
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        exposure = max(0.0, 1.0 - abs(brightness - 127.5) / 127.5)
        contrast = min(1.0, float(gray.std()) / 45.0)
        sharpness = min(1.0, float(cv2.Laplacian(gray, cv2.CV_32F).var()) / 180.0)
        resolution = min(1.0, min(height, width) / 160.0)
        return round(0.30 * exposure + 0.20 * contrast + 0.35 * sharpness + 0.15 * resolution, 4)

    def _descriptor(self, image: np.ndarray) -> Descriptor:
        if self._embedding_network is not None:
            resized = cv2.resize(image, (224, 224), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            deviation = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            blob = ((rgb - mean) / deviation).transpose(2, 0, 1)[None, ...]
            self._embedding_network.setInput(blob)
            embedding = self._embedding_network.forward("onnx_node!Reshape_103").flatten()
            return embedding / max(float(np.linalg.norm(embedding)), 1e-8)
        return self._appearance_descriptor(image)

    @staticmethod
    def _appearance_descriptor(image: np.ndarray) -> Descriptor:
        resized = cv2.resize(image, (128, 128), interpolation=cv2.INTER_AREA)
        lab = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
        normalized = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        hsv = cv2.cvtColor(normalized, cv2.COLOR_BGR2HSV)
        histograms: list[np.ndarray] = []
        for rows, columns in ((1, 1), (2, 2)):
            for row in range(rows):
                for column in range(columns):
                    cell = hsv[row * 128 // rows:(row + 1) * 128 // rows,
                               column * 128 // columns:(column + 1) * 128 // columns]
                    histogram = cv2.calcHist([cell], [0, 1], None, [18, 10], [0, 180, 0, 256]).flatten()
                    histograms.append(histogram / max(float(histogram.sum()), 1.0))
        color = np.concatenate(histograms).astype(np.float32)
        gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
        hog = cv2.HOGDescriptor((128, 128), (32, 32), (16, 16), (16, 16), 9).compute(gray).flatten()
        hog /= max(float(np.linalg.norm(hog)), 1e-8)
        lab_float = lab.astype(np.float32) / 255.0
        statistics = np.concatenate((lab_float.mean(axis=(0, 1)), lab_float.std(axis=(0, 1))))
        return color, hog.astype(np.float32), statistics.astype(np.float32)

    @staticmethod
    def _cosine(first: np.ndarray, second: np.ndarray) -> float:
        denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
        return float(np.dot(first, second) / denominator) if denominator else 1.0

    @classmethod
    def _similarity(cls, first: Descriptor, second: Descriptor) -> float:
        if isinstance(first, np.ndarray) and isinstance(second, np.ndarray):
            return float(np.clip(np.dot(first, second), 0.0, 1.0))
        if isinstance(first, np.ndarray) or isinstance(second, np.ndarray):
            return 0.0
        color = max(0.0, cls._cosine(first[0], second[0]))
        texture = max(0.0, cls._cosine(first[1], second[1]))
        distance = float(np.linalg.norm(first[2] - second[2]) / np.sqrt(len(first[2])))
        return float(np.clip(color * 0.50 + texture * 0.35 + max(0.0, 1.0 - distance) * 0.15, 0.0, 1.0))

    @classmethod
    def _gallery_score(cls, capture: Descriptor, references: list[Descriptor]) -> float:
        return max(cls._similarity(capture, item) for item in references)
