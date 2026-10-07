from __future__ import annotations

import cv2
import numpy as np

MOTION_THRESHOLD = 4.0
SAMPLE_SIZE = (64, 36)


class MotionGate:
    def __init__(self, threshold: float = MOTION_THRESHOLD) -> None:
        self.threshold = threshold
        self._previous: np.ndarray | None = None

    def changed(self, frame: np.ndarray) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        current = cv2.GaussianBlur(cv2.resize(gray, SAMPLE_SIZE, interpolation=cv2.INTER_AREA), (3, 3), 0)
        previous, self._previous = self._previous, current
        if previous is None:
            return True
        return float(cv2.absdiff(current, previous).mean()) > self.threshold
