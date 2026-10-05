from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from app.core.config import CLIP_DIR, DATA_DIR

JPEG_QUALITY = 78
MAX_FRAME_WIDTH = 960


class ClipStore:
    def __init__(self, data_dir: Path = DATA_DIR, clip_dir: Path = CLIP_DIR) -> None:
        self.data_dir = data_dir
        self.clip_dir = clip_dir

    def encode(self, frame: np.ndarray, max_width: int = MAX_FRAME_WIDTH) -> bytes | None:
        prepared = frame
        if frame.shape[1] > max_width:
            scale = max_width / frame.shape[1]
            prepared = cv2.resize(frame, (max_width, round(frame.shape[0] * scale)))
        encoded, jpeg = cv2.imencode(".jpg", prepared, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        return jpeg.tobytes() if encoded else None

    def save(self, frames: list[bytes], captured_at: datetime, fps: float = 3.0) -> str | None:
        if len(frames) < 2:
            return None
        first_frame = cv2.imdecode(np.frombuffer(frames[0], dtype=np.uint8), cv2.IMREAD_COLOR)
        if first_frame is None:
            return None
        height, width = first_frame.shape[:2]
        directory = self.clip_dir / captured_at.strftime("%Y/%m/%d")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid4()}.webm"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"VP80"), fps, (width, height))
        if not writer.isOpened():
            return None
        try:
            writer.write(first_frame)
            for encoded_frame in frames[1:]:
                frame = cv2.imdecode(np.frombuffer(encoded_frame, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                writer.write(frame)
        finally:
            writer.release()
        if not path.is_file() or path.stat().st_size == 0:
            return None
        return path.relative_to(self.data_dir).as_posix()

    def resolve(self, relative_path: str) -> Path:
        path = (self.data_dir / relative_path).resolve()
        if self.data_dir.resolve() not in path.parents:
            raise ValueError("Caminho de vídeo inválido.")
        return path
