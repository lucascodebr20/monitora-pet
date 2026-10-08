from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.infra.ai.pet_identifier import PetIdentifier

MAX_PET_OBSERVATIONS = 10
OBSERVATION_INTERVAL_SECONDS = 0.75
MAX_CAPTURE_EDGE = 320
MINIMUM_QUALITY = 0.5
DUPLICATE_DISTANCE = 0.025


@dataclass
class Observation:
    image: np.ndarray
    signature: np.ndarray
    quality: float


@dataclass
class PetObservations:
    samples: list[Observation] = field(default_factory=list)
    last_sample_at: float | None = None

    @property
    def images(self) -> list[np.ndarray]:
        qualified = [sample for sample in self.samples if sample.quality >= MINIMUM_QUALITY]
        chosen = qualified or sorted(self.samples, key=lambda sample: sample.quality, reverse=True)[:1]
        return [sample.image for sample in chosen]

    def clear(self) -> None:
        self.samples.clear()
        self.last_sample_at = None

    def due(self, now: float) -> bool:
        return self.last_sample_at is None or now - self.last_sample_at >= OBSERVATION_INTERVAL_SECONDS

    def add(self, image: np.ndarray, now: float) -> None:
        if image.size == 0 or not self.due(now):
            return
        self.last_sample_at = now
        height, width = image.shape[:2]
        scale = min(1.0, MAX_CAPTURE_EDGE / max(height, width))
        image = cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
        sample = Observation(image, cv2.resize(image, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0,
                             PetIdentifier.image_quality(image))
        nearest_index = min(range(len(self.samples)), key=lambda index: self.distance(sample, self.samples[index]), default=None)
        if nearest_index is not None and self.distance(sample, self.samples[nearest_index]) < DUPLICATE_DISTANCE:
            if sample.quality > self.samples[nearest_index].quality:
                self.samples[nearest_index] = sample
            return
        if sample.quality < MINIMUM_QUALITY:
            if not self.samples:
                self.samples.append(sample)
            elif all(other.quality < MINIMUM_QUALITY for other in self.samples) and sample.quality > self.samples[0].quality:
                self.samples[:] = [sample]
            return
        self.samples = [other for other in self.samples if other.quality >= MINIMUM_QUALITY]
        self.samples.append(sample)
        if len(self.samples) > MAX_PET_OBSERVATIONS:
            remaining = self.samples.copy()
            selected = [remaining.pop(max(range(len(remaining)), key=lambda index: remaining[index].quality))]
            while remaining and len(selected) < MAX_PET_OBSERVATIONS:
                index = max(range(len(remaining)), key=lambda index:
                            remaining[index].quality * 0.6 + min(self.distance(remaining[index], other) for other in selected) * 0.4)
                selected.append(remaining.pop(index))
            self.samples = selected

    @staticmethod
    def distance(first: Observation, second: Observation) -> float:
        return float(np.mean(np.abs(first.signature - second.signature)))
