from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

MAX_FILE_BYTES = 25_000_000
THUMBNAIL_EDGE = 480
THUMBNAIL_QUALITY = 82

SIGNATURES = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
)


@dataclass(frozen=True)
class StoredFile:
    file_path: str
    thumbnail_path: str | None
    media_type: str
    size_bytes: int
    sha256: str


class HealthFileStore:
    def __init__(self, data_dir: Path, health_dir: Path) -> None:
        self.data_dir = data_dir
        self.health_dir = health_dir

    @staticmethod
    def detect(content: bytes) -> tuple[str, str] | None:
        for signature, media_type, extension in SIGNATURES:
            if content.startswith(signature):
                return media_type, extension
        if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "image/webp", ".webp"
        return None

    def save(self, content: bytes) -> StoredFile:
        if not content:
            raise ValueError("O arquivo enviado está vazio.")
        if len(content) > MAX_FILE_BYTES:
            raise ValueError("O arquivo deve ter até 25 MB.")
        detected = self.detect(content)
        if not detected:
            raise ValueError("Envie um PDF ou uma imagem (JPEG, PNG ou WebP).")
        media_type, extension = detected
        directory = self.health_dir / datetime.now(timezone.utc).strftime("%Y/%m")
        directory.mkdir(parents=True, exist_ok=True)
        name = str(uuid4())
        path = directory / f"{name}{extension}"
        temporary = directory / f".{name}.tmp"
        temporary.write_bytes(content)
        os.replace(temporary, path)
        try:
            thumbnail = (self._thumbnail(content, directory / f"{name}.thumb.jpg")
                         if media_type != "application/pdf" else None)
        except ValueError:
            path.unlink(missing_ok=True)
            raise
        return StoredFile(
            self._relative(path), self._relative(thumbnail) if thumbnail else None,
            media_type, len(content), hashlib.sha256(content).hexdigest(),
        )

    def _thumbnail(self, content: bytes, target: Path) -> Path | None:
        image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Não foi possível abrir a imagem enviada.")
        height, width = image.shape[:2]
        scale = min(1.0, THUMBNAIL_EDGE / max(height, width))
        if scale < 1.0:
            image = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
        encoded, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, THUMBNAIL_QUALITY])
        if not encoded:
            return None
        target.write_bytes(data.tobytes())
        return target

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.data_dir).as_posix()

    def resolve(self, relative_path: str) -> Path:
        path = (self.data_dir / relative_path).resolve()
        if self.health_dir.resolve() not in path.parents:
            raise ValueError("Caminho de arquivo inválido.")
        return path

    def remove(self, relative_paths: list[str | None]) -> None:
        for relative in relative_paths:
            if not relative:
                continue
            try:
                self.resolve(relative).unlink(missing_ok=True)
            except (OSError, ValueError):
                continue
