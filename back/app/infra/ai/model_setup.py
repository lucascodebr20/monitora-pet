from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

from app.core.config import APP_VERSION, MODEL_PATH, PET_EMBEDDING_MODEL_PATH, ensure_data_directories


MODEL_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx"
MODEL_SHA256 = "427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7"
PET_EMBEDDING_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "image_classification_mobilenet/image_classification_mobilenetv2_2022apr.onnx"
)
PET_EMBEDDING_MODEL_SHA256 = "c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_download(path: Path, url: str, sha256: str) -> Path:
    if path.exists() and file_hash(path) == sha256:
        return path
    temporary = path.with_suffix(".download")
    request = Request(url, headers={"User-Agent": f"VigiaPet/{APP_VERSION}"})
    try:
        with urlopen(request, timeout=60) as response, temporary.open("wb") as target:
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
        if file_hash(temporary) != sha256:
            raise RuntimeError("O modelo de IA baixado não passou na validação de integridade.")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def ensure_models() -> tuple[Path, Path]:
    ensure_data_directories()
    detector = ensure_download(MODEL_PATH, MODEL_URL, MODEL_SHA256)
    embedding = ensure_download(
        PET_EMBEDDING_MODEL_PATH, PET_EMBEDDING_MODEL_URL, PET_EMBEDDING_MODEL_SHA256
    )
    return detector, embedding


if __name__ == "__main__":
    paths = ensure_models()
    print(f"Modelos de IA disponíveis em {', '.join(str(path) for path in paths)}")
