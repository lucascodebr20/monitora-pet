from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.domain.clock import utc_now
from app.domain.enums import ReviewDecision
from app.domain.errors import InvalidDomainValueError
from app.infra.ai.identification_calibration import METHOD, Sample, search_thresholds
from app.infra.repositories.event_repository import EventRepository
from app.infra.repositories.pet_identification_repository import PetIdentificationRepository
from app.infra.repositories.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)

ENABLED_KEY = "auto_review_enabled"
TARGET_PRECISION_KEY = "auto_review_target_precision"

DEFAULT_TARGET_PRECISION = 0.97
MIN_TARGET_PRECISION = 0.90
MAX_TARGET_PRECISION = 0.99

# Abaixo disso a precisao medida nao tem evidencia suficiente para dispensar a
# revisao humana: com poucas amostras o intervalo de confianca e largo demais.
MINIMUM_SAMPLES = 40


class AutoReviewService:
    """Decide quais identificacoes sao boas o bastante para pular a revisao.

    O portao e separado do que decide se o sistema mostra um palpite. Aquele
    pode ser permissivo, porque voce confere; este nao, porque ninguem confere.

    Duas coisas que uma revisao automatica nunca faz, para nao realimentar o
    identificador com os proprios palpites:

    - nao marca a analise como revisada, entao a calibracao e a taxa de acerto
      continuam medidas so com decisoes humanas;
    - nao vira imagem de referencia do pet, senao um erro contaminaria a
      galeria usada nas comparacoes seguintes.
    """

    def __init__(
        self,
        settings: SettingsRepository,
        event_repository: EventRepository,
        identification_repository: PetIdentificationRepository | None,
    ) -> None:
        self.settings = settings
        self.event_repository = event_repository
        self.identification_repository = identification_repository

    def enabled(self) -> bool:
        return bool(self.settings.get(ENABLED_KEY, False))

    def target_precision(self) -> float:
        value = self.settings.get(TARGET_PRECISION_KEY, DEFAULT_TARGET_PRECISION)
        try:
            return min(MAX_TARGET_PRECISION, max(MIN_TARGET_PRECISION, float(value)))
        except (TypeError, ValueError):
            return DEFAULT_TARGET_PRECISION

    def update(self, enabled: bool | None, target_precision: float | None) -> None:
        if target_precision is not None:
            if not MIN_TARGET_PRECISION <= target_precision <= MAX_TARGET_PRECISION:
                raise InvalidDomainValueError(
                    f"A precisão-alvo deve ficar entre {MIN_TARGET_PRECISION:.0%} e {MAX_TARGET_PRECISION:.0%}."
                )
            self.settings.set(TARGET_PRECISION_KEY, round(target_precision, 4))
        if enabled is not None:
            self.settings.set(ENABLED_KEY, bool(enabled))

    def samples(self) -> list[Sample]:
        """(confianca, margem sobre o segundo, acertou) de cada revisão humana."""
        if not self.identification_repository:
            return []
        collected: list[Sample] = []
        for sample in self.identification_repository.reviewed_samples(METHOD):
            scores = sorted(
                (float(score["confidence"]) for score in sample["scores"]), reverse=True
            )
            if not scores:
                continue
            top = sorted(
                ((score["pet_id"], float(score["confidence"])) for score in sample["scores"]),
                key=lambda item: item[1],
                reverse=True,
            )
            runner_up = scores[1] if len(scores) > 1 else 0.0
            collected.append((scores[0], scores[0] - runner_up, top[0][0] == sample["reviewed_pet_id"]))
        return collected

    def thresholds(self) -> tuple[float, float] | None:
        """Limiares que sustentam a precisão-alvo, ou None se ainda não dá."""
        collected = self.samples()
        if len(collected) < MINIMUM_SAMPLES:
            return None
        return search_thresholds(collected, self.target_precision())

    def should_confirm(self, pet_id: str | None, confidence: float | None, margin: float | None) -> bool:
        if not self.enabled() or not pet_id or confidence is None or margin is None:
            return False
        thresholds = self.thresholds()
        if thresholds is None:
            return False
        minimum_similarity, minimum_margin = thresholds
        return confidence >= minimum_similarity and margin >= minimum_margin

    def confirm(self, event_id: str, pet_id: str) -> None:
        """Registra a revisão automática. Silenciosa: nunca interrompe a captura."""
        try:
            self.event_repository.complete_automatic_review(
                {
                    "id": str(uuid4()),
                    "event_id": event_id,
                    "decision": ReviewDecision.CONFIRMED.value,
                    "corrected_activity": None,
                    "cat_name": None,
                    "notes": "Revisão automática",
                    "created_at": utc_now(),
                    "pet_id": pet_id,
                },
                pet_id,
            )
        except Exception:  # noqa: BLE001 - a revisão é um extra, o evento já está gravado
            logger.exception("Não foi possível concluir a revisão automática do evento %s", event_id)

    def view(self) -> dict[str, Any]:
        collected = self.samples()
        thresholds = self.thresholds()
        payload: dict[str, Any] = {
            "auto_review_enabled": self.enabled(),
            "auto_review_target_precision": self.target_precision(),
            "auto_review_sample_count": len(collected),
            "auto_review_minimum_samples": MINIMUM_SAMPLES,
            "auto_review_minimum_similarity": None,
            "auto_review_minimum_margin": None,
            "auto_review_expected_coverage": None,
            "auto_review_expected_precision": None,
        }
        if thresholds is None:
            return payload
        minimum_similarity, minimum_margin = thresholds
        accepted = [
            correct
            for confidence, margin, correct in collected
            if confidence >= minimum_similarity and margin >= minimum_margin
        ]
        payload["auto_review_minimum_similarity"] = minimum_similarity
        payload["auto_review_minimum_margin"] = minimum_margin
        if accepted:
            payload["auto_review_expected_coverage"] = round(len(accepted) / len(collected), 4)
            payload["auto_review_expected_precision"] = round(sum(accepted) / len(accepted), 4)
        return payload
