from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

from app.core.config import MODEL_PATH, ensure_data_directories


MODEL_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx"
MODEL_SHA256 = "427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model() -> Path:
    ensure_data_directories()
    if MODEL_PATH.exists() and file_hash(MODEL_PATH) == MODEL_SHA256:
        return MODEL_PATH
    temporary = MODEL_PATH.with_suffix(".download")
    request = Request(MODEL_URL, headers={"User-Agent": "MonitoraPet"})
    try:
        with urlopen(request, timeout=60) as response, temporary.open("wb") as target:
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
        if file_hash(temporary) != MODEL_SHA256:
            raise RuntimeError("O modelo de IA baixado não passou na validação de integridade.")
        temporary.replace(MODEL_PATH)
    finally:
        if temporary.exists():
            temporary.unlink()
    return MODEL_PATH


if __name__ == "__main__":
    path = ensure_model()
    print(f"Modelo de IA disponível em {path}")
