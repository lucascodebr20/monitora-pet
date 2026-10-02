from dataclasses import dataclass
from enum import StrEnum


class PresenceState(StrEnum):
    OUTSIDE = "OUTSIDE"
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"


class TransitionType(StrEnum):
    CONFIRM = "CONFIRM"
    FINISH = "FINISH"


@dataclass(frozen=True)
class PresenceTransition:
    type: TransitionType
    elapsed_seconds: float
    confidence: float
    seconds_since_seen: float


class ZonePresenceMachine:
    def __init__(self) -> None:
        self.state = PresenceState.OUTSIDE
        self.entered_at = 0.0
        self.last_seen_at = 0.0
        self.confidence = 0.0

    def observe(
        self,
        present: bool,
        confidence: float,
        now: float,
        minimum_presence: float,
        absence_tolerance: float,
        cooldown: float,
    ) -> list[PresenceTransition]:
        transitions: list[PresenceTransition] = []
        if self.state == PresenceState.OUTSIDE:
            if present:
                self.state = PresenceState.CANDIDATE
                self.entered_at = now
                self.last_seen_at = now
                self.confidence = confidence
            return transitions

        if present:
            self.last_seen_at = now
            self.confidence = max(self.confidence, confidence)
            if self.state == PresenceState.COOLDOWN:
                self.state = PresenceState.ACTIVE
            if self.state == PresenceState.CANDIDATE and now - self.entered_at >= minimum_presence:
                self.state = PresenceState.ACTIVE
                transitions.append(
                    PresenceTransition(
                        TransitionType.CONFIRM,
                        now - self.entered_at,
                        self.confidence,
                        0.0,
                    )
                )
            return transitions

        seconds_since_seen = now - self.last_seen_at
        if self.state == PresenceState.CANDIDATE and seconds_since_seen > absence_tolerance:
            self.reset()
        elif self.state == PresenceState.ACTIVE and seconds_since_seen > absence_tolerance:
            self.state = PresenceState.COOLDOWN
        elif self.state == PresenceState.COOLDOWN and seconds_since_seen >= cooldown:
            transitions.append(
                PresenceTransition(
                    TransitionType.FINISH,
                    self.last_seen_at - self.entered_at,
                    self.confidence,
                    seconds_since_seen,
                )
            )
            self.reset()
        return transitions

    def elapsed(self, now: float) -> float:
        if self.state == PresenceState.OUTSIDE:
            return 0.0
        return max(0.0, now - self.entered_at)

    def reset(self) -> None:
        self.state = PresenceState.OUTSIDE
        self.entered_at = 0.0
        self.last_seen_at = 0.0
        self.confidence = 0.0
