from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

DEFAULT_FPS = 25.0


class RecordingUnreadableError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecordingInfo:
    duration_seconds: float
    fps: float
    frame_count: int
    width: int
    height: int


def index_path_for(path: Path) -> Path:
    return path.with_name(path.name + ".index.json")


class RecordingReader:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._timestamps: list[float] | None = None

    def timestamps(self) -> list[float]:
        if self._timestamps is None:
            index = index_path_for(self.path)
            self._timestamps = []
            if index.is_file():
                try:
                    values = json.loads(index.read_text(encoding="utf-8")).get("timestamps", [])
                    self._timestamps = [float(value) for value in values]
                except (OSError, ValueError):
                    self._timestamps = []
        return self._timestamps

    def probe(self) -> RecordingInfo:
        capture = self._open()
        try:
            fps = capture.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            stamps = self.timestamps()
            if stamps:
                frame_count = len(stamps)
                span = stamps[-1] - stamps[0]
                if len(stamps) > 1 and span > 0:
                    fps = (len(stamps) - 1) / span
                return RecordingInfo(span + 1 / fps, fps, frame_count, width, height)
            if frame_count <= 0:
                frame_count = self._count_frames(capture)
        finally:
            capture.release()
        if frame_count <= 0:
            raise RecordingUnreadableError("A gravação não contém quadros legíveis.")
        return RecordingInfo(frame_count / fps, fps, frame_count, width, height)

    def frames(self, sample_fps: float) -> Iterator[tuple[float, np.ndarray]]:
        capture = self._open()
        stamps = self.timestamps()
        try:
            fps = capture.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
            if len(stamps) > 1 and stamps[-1] > stamps[0]:
                fps = (len(stamps) - 1) / (stamps[-1] - stamps[0])
            stride = max(1, round(fps / sample_fps))
            index = 0
            while capture.grab():
                if index % stride == 0:
                    ok, frame = capture.retrieve()
                    if ok and frame is not None:
                        yield self._offset(index, fps, stamps), frame
                index += 1
        finally:
            capture.release()

    def first_frame(self) -> np.ndarray | None:
        for _, frame in self.frames(sample_fps=1_000_000):
            return frame
        return None

    @staticmethod
    def _offset(index: int, fps: float, stamps: list[float]) -> float:
        if index < len(stamps):
            return stamps[index] - stamps[0]
        return index / fps

    def _open(self) -> cv2.VideoCapture:
        if not self.path.is_file():
            raise RecordingUnreadableError("O arquivo da gravação não foi encontrado.")
        capture = cv2.VideoCapture(str(self.path), cv2.CAP_FFMPEG)
        if not capture.isOpened():
            capture.release()
            raise RecordingUnreadableError("Não foi possível abrir a gravação. Formato ou codec não suportado.")
        return capture

    @staticmethod
    def _count_frames(capture: cv2.VideoCapture) -> int:
        count = 0
        while capture.grab():
            count += 1
        return count
