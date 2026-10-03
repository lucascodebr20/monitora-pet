from __future__ import annotations

import base64
import binascii
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from app.core.config import DATA_DIR, PET_IMAGE_DIR
from app.domain.detection import Detection


class PetImageStore:
    def save_data_url(self, data_url: str) -> str:
        if "," not in data_url or not data_url.startswith("data:image/"):
            raise ValueError("Envie uma imagem válida.")
        try:
            content = base64.b64decode(data_url.split(",", 1)[1], validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("Não foi possível ler a imagem enviada.") from error
        if not content or len(content) > 8_000_000:
            raise ValueError("A imagem deve ter até 8 MB.")
        image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("O arquivo enviado não é uma imagem compatível.")
        return self.save_image(image, "profiles")

    def save_capture(self, frame: np.ndarray, detection: Detection) -> str | None:
        height, width = frame.shape[:2]
        padding_x = (detection.x2 - detection.x1) * 0.12
        padding_y = (detection.y2 - detection.y1) * 0.12
        x1 = max(0, int((detection.x1 - padding_x) * width))
        y1 = max(0, int((detection.y1 - padding_y) * height))
        x2 = min(width, int((detection.x2 + padding_x) * width))
        y2 = min(height, int((detection.y2 + padding_y) * height))
        crop = frame[y1:y2, x1:x2]
        return self.save_image(crop, "captures") if crop.size else None

    def save_image(self, image: np.ndarray, category: str) -> str:
        directory = PET_IMAGE_DIR / category / datetime.now().strftime("%Y/%m/%d")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid4()}.jpg"
        encoded, content = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not encoded:
            raise ValueError("Não foi possível salvar a imagem.")
        path.write_bytes(content.tobytes())
        return path.relative_to(DATA_DIR).as_posix()

    def resolve(self, relative_path: str) -> Path:
        path = (DATA_DIR / relative_path).resolve()
        if DATA_DIR.resolve() not in path.parents:
            raise ValueError("Caminho de imagem inválido.")
        return path
