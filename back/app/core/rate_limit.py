from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

MAX_FAILURES = 5
WINDOW_SECONDS = 60.0
LOCK_SECONDS = 30.0
MAX_LOCK_SECONDS = 15 * 60.0
MAX_TRACKED_ORIGINS = 2000


@dataclass
class _Origin:
    failures: list[float] = field(default_factory=list)
    locked_until: float = 0.0
    lockouts: int = 0


class FailedAttemptLimiter:
    def __init__(
        self,
        max_failures: int = MAX_FAILURES,
        window_seconds: float = WINDOW_SECONDS,
        lock_seconds: float = LOCK_SECONDS,
        max_lock_seconds: float = MAX_LOCK_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lock_seconds = lock_seconds
        self.max_lock_seconds = max_lock_seconds
        self.clock = clock
        self._origins: dict[str, _Origin] = {}
        self._lock = threading.Lock()

    def seconds_locked(self, origin: str) -> float:
        with self._lock:
            entry = self._origins.get(origin)
            if entry is None:
                return 0.0
            return max(0.0, entry.locked_until - self.clock())

    def record_failure(self, origin: str) -> float:
        now = self.clock()
        with self._lock:
            self._prune(now)
            entry = self._origins.setdefault(origin, _Origin())
            entry.failures = [moment for moment in entry.failures if now - moment < self.window_seconds]
            entry.failures.append(now)
            if len(entry.failures) < self.max_failures:
                return 0.0
            entry.lockouts += 1
            duration = min(self.lock_seconds * (2 ** (entry.lockouts - 1)), self.max_lock_seconds)
            entry.locked_until = now + duration
            entry.failures.clear()
            return duration

    def reset(self, origin: str) -> None:
        with self._lock:
            self._origins.pop(origin, None)

    def _prune(self, now: float) -> None:
        if len(self._origins) < MAX_TRACKED_ORIGINS:
            return
        stale = [
            origin for origin, entry in self._origins.items()
            if entry.locked_until <= now and all(now - moment >= self.window_seconds for moment in entry.failures)
        ]
        for origin in stale:
            del self._origins[origin]
