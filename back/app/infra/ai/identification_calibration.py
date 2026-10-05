from __future__ import annotations

from app.infra.repositories.pet_identification_repository import PetIdentificationRepository

METHOD = "mobilenet-embedding-v2"
MINIMUM_SIMILARITY = 0.731
MINIMUM_MARGIN = 0.064
CALIBRATION_INTERVAL = 10
TARGET_PRECISION = 0.80

Sample = tuple[float, float, bool]


class IdentificationCalibrator:
    METHOD = METHOD
    MINIMUM_SIMILARITY = MINIMUM_SIMILARITY
    MINIMUM_MARGIN = MINIMUM_MARGIN
    CALIBRATION_INTERVAL = CALIBRATION_INTERVAL

    def __init__(self, repository: PetIdentificationRepository | None) -> None:
        self.repository = repository

    def thresholds(self) -> tuple[float, float]:
        if not self.repository:
            return MINIMUM_SIMILARITY, MINIMUM_MARGIN
        calibration = self.repository.current_calibration(METHOD)
        if not calibration.get("created_at"):
            return MINIMUM_SIMILARITY, MINIMUM_MARGIN
        return float(calibration["minimum_similarity"]), float(calibration["minimum_margin"])

    def interactions_until_next(self) -> int:
        if not self.repository:
            return CALIBRATION_INTERVAL
        calibration = self.repository.current_calibration(METHOD)
        progress = self.repository.reviewed_count(METHOD) - int(calibration["interaction_count"])
        return max(0, CALIBRATION_INTERVAL - progress)

    def learn_from_review(self, event_id: str, pet_id: str) -> None:
        if not self.repository or not self.repository.mark_review(event_id, pet_id):
            return
        reviewed_count = self.repository.reviewed_count(METHOD)
        current = self.repository.current_calibration(METHOD)
        if reviewed_count - int(current["interaction_count"]) < CALIBRATION_INTERVAL:
            return
        samples: list[Sample] = []
        top1_correct = 0
        for sample in self.repository.reviewed_samples(METHOD):
            scores = sorted(
                ((score["pet_id"], float(score["confidence"])) for score in sample["scores"]),
                key=lambda item: item[1], reverse=True,
            )
            if not scores:
                continue
            is_correct = scores[0][0] == sample["reviewed_pet_id"]
            top1_correct += int(is_correct)
            runner_up = scores[1][1] if len(scores) > 1 else 0.0
            samples.append((scores[0][1], scores[0][1] - runner_up, is_correct))
        if not samples:
            return
        minimum_similarity, minimum_margin = self.choose_thresholds(samples)
        self.repository.create_calibration(
            minimum_similarity, minimum_margin, reviewed_count, round(top1_correct / len(samples), 4), METHOD,
        )

    @staticmethod
    def choose_thresholds(samples: list[Sample]) -> tuple[float, float]:
        similarities = sorted({MINIMUM_SIMILARITY, *(round(item[0], 3) for item in samples)})
        margins = sorted({MINIMUM_MARGIN, *(round(max(0.0, item[1]), 3) for item in samples)})
        best: tuple[float, float, float, float] | None = None
        for similarity in similarities:
            for margin in margins:
                accepted = [item for item in samples if item[0] >= similarity and item[1] >= margin]
                if not accepted:
                    continue
                precision = sum(item[2] for item in accepted) / len(accepted)
                coverage = len(accepted) / len(samples)
                candidate = (coverage, precision, -similarity, -margin)
                if precision >= TARGET_PRECISION and (best is None or candidate > best):
                    best = candidate
        if best is None:
            return MINIMUM_SIMILARITY, MINIMUM_MARGIN
        return round(-best[2], 4), round(-best[3], 4)
