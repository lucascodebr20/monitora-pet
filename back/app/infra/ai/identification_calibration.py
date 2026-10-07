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

    def thresholds(self, species: str) -> tuple[float, float]:
        if not self.repository:
            return MINIMUM_SIMILARITY, MINIMUM_MARGIN
        calibration = self.repository.current_calibration(METHOD, species)
        if not calibration.get("created_at"):
            return MINIMUM_SIMILARITY, MINIMUM_MARGIN
        return float(calibration["minimum_similarity"]), float(calibration["minimum_margin"])

    def interactions_until_next(self, species: str) -> int:
        if not self.repository:
            return CALIBRATION_INTERVAL
        calibration = self.repository.current_calibration(METHOD, species)
        progress = self.repository.reviewed_count(METHOD, species) - int(calibration["interaction_count"])
        return max(0, CALIBRATION_INTERVAL - progress)

    def learn_from_review(self, event_id: str, pet_id: str) -> None:
        species = self.repository.mark_review(event_id, pet_id) if self.repository else None
        if not species:
            return
        reviewed_count = self.repository.reviewed_count(METHOD, species)
        current = self.repository.current_calibration(METHOD, species)
        if reviewed_count - int(current["interaction_count"]) < CALIBRATION_INTERVAL:
            return
        samples: list[Sample] = []
        top1_correct = 0
        for sample in self.repository.reviewed_samples(METHOD, species):
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
            minimum_similarity, minimum_margin, reviewed_count, round(top1_correct / len(samples), 4), METHOD, species,
        )

    @staticmethod
    def choose_thresholds(samples: list[Sample]) -> tuple[float, float]:
        best = search_thresholds(samples, TARGET_PRECISION)
        if best is None:
            return MINIMUM_SIMILARITY, MINIMUM_MARGIN
        return best


def search_thresholds(samples: list[Sample], target_precision: float) -> tuple[float, float] | None:
    """Menor par (similaridade, margem) que atinge a precisao pedida.

    Varre os limiares observados nas proprias amostras revisadas e escolhe o
    par que aceita o maior numero delas sem cair abaixo de `target_precision`.
    Devolve None quando nenhum par alcanca o alvo — o chamador decide se cai
    para um padrao ou se simplesmente nao age.
    """
    if not samples:
        return None
    similarities = sorted({MINIMUM_SIMILARITY, *(round(item[0], 3) for item in samples)})
    margins = sorted({MINIMUM_MARGIN, *(round(max(0.0, item[1]), 3) for item in samples)})
    best: tuple[float, float, float, float] | None = None
    for similarity in similarities:
        for margin in margins:
            accepted = [item for item in samples if item[0] >= similarity and item[1] >= margin]
            if not accepted:
                continue
            precision = sum(item[2] for item in accepted) / len(accepted)
            if precision < target_precision:
                continue
            candidate = (len(accepted) / len(samples), precision, -similarity, -margin)
            if best is None or candidate > best:
                best = candidate
    if best is None:
        return None
    return round(-best[2], 4), round(-best[3], 4)
