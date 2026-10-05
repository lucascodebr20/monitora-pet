from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

import numpy as np

from app.infra.media.clip_store import ClipStore
from app.infra.repositories.event_repository import EventRepository

logger = logging.getLogger(__name__)

CLIP_FPS = 3.0
MAX_CLIP_SECONDS = 300
MAX_CLIP_FRAMES = round(CLIP_FPS * MAX_CLIP_SECONDS)
MAX_CLIP_BUFFER_BYTES = 150 * 1024 * 1024


@dataclass
class ClipBuffer:
    frames: list[bytes] = field(default_factory=list)
    path: str | None = None
    started_at: float | None = None
    event_id: str | None = None

    @property
    def size(self) -> int:
        return sum(len(frame) for frame in self.frames)

    def elapsed(self, now: float) -> float:
        return now - self.started_at if self.started_at is not None else 0.0

    def accepting(self, now: float) -> bool:
        return self.path is None and self.elapsed(now) <= MAX_CLIP_SECONDS and len(self.frames) < MAX_CLIP_FRAMES

    def exhausted(self, now: float) -> bool:
        return self.elapsed(now) >= MAX_CLIP_SECONDS or len(self.frames) >= MAX_CLIP_FRAMES

    def reset(self, started_at: float | None = None) -> None:
        self.frames.clear()
        self.path = None
        self.started_at = started_at
        self.event_id = None


class ClipRecorder:
    def __init__(self, clip_store: ClipStore, event_repository: EventRepository) -> None:
        self.clip_store = clip_store
        self.event_repository = event_repository

    def capture(
        self,
        buffer: ClipBuffer,
        frame: np.ndarray,
        now: float,
        now_utc: datetime,
        peers: Iterable[ClipBuffer],
    ) -> None:
        if not buffer.accepting(now):
            return
        encoded = self.clip_store.encode(frame)
        if not encoded:
            return
        peers = list(peers)
        if self.total_bytes(peers) + len(encoded) > MAX_CLIP_BUFFER_BYTES:
            self._relieve(peers, now_utc)
            if not buffer.accepting(now) or self.total_bytes(peers) + len(encoded) > MAX_CLIP_BUFFER_BYTES:
                return
        buffer.frames.append(encoded)

    def finalize(self, buffer: ClipBuffer, captured_at: datetime) -> None:
        if not buffer.event_id or buffer.path or len(buffer.frames) < 2:
            return
        path = self.clip_store.save(buffer.frames, captured_at, CLIP_FPS)
        if path:
            self.event_repository.attach_clip(buffer.event_id, path)
            buffer.path = path
            buffer.frames.clear()

    @staticmethod
    def total_bytes(buffers: Iterable[ClipBuffer]) -> int:
        return sum(buffer.size for buffer in buffers)

    def _relieve(self, buffers: list[ClipBuffer], now_utc: datetime) -> None:
        heaviest = max((buffer for buffer in buffers if buffer.frames), key=lambda buffer: buffer.size, default=None)
        if heaviest is None:
            return
        if heaviest.event_id and not heaviest.path:
            logger.warning("Limite de memória de clipes atingido; vídeo do evento %s encerrado mais cedo", heaviest.event_id)
            self.finalize(heaviest, now_utc)
        heaviest.frames.clear()
