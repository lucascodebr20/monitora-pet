from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from app.core.config import CLIP_DIR, DATA_DIR


class ClipStore:
    def encode(self, frame: np.ndarray, max_width: int = 960) -> bytes | None:
        prepared = frame
        if frame.shape[1] > max_width:
            scale = max_width / frame.shape[1]
            prepared = cv2.resize(frame, (max_width, round(frame.shape[0] * scale)))
        encoded, jpeg = cv2.imencode(".jpg", prepared, [cv2.IMWRITE_JPEG_QUALITY, 78])
        return jpeg.tobytes() if encoded else None

    def save(self, frames: list[bytes], captured_at: datetime, fps: float = 3.0) -> str | None:
        decoded = [cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR) for frame in frames]
        decoded = [frame for frame in decoded if frame is not None]
        if len(decoded) < 2:
            return None
        height, width = decoded[0].shape[:2]
        directory = CLIP_DIR / captured_at.strftime("%Y/%m/%d")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid4()}.webm"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"VP80"), fps, (width, height))
        if not writer.isOpened():
            return None
        try:
            for frame in decoded:
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                writer.write(frame)
        finally:
            writer.release()
        if not path.is_file() or path.stat().st_size == 0:
            return None
        return path.relative_to(DATA_DIR).as_posix()

    def resolve(self, relative_path: str) -> Path:
        path = (DATA_DIR / relative_path).resolve()
        if DATA_DIR.resolve() not in path.parents:
            raise ValueError("Caminho de vídeo inválido.")
        return path
