from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "VigiaPet"
APP_VERSION = "0.2.0"
BACK_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACK_DIR.parent


def _frontend_dist() -> Path:
    configured = os.getenv("VIGIAPET_FRONTEND_DIST")
    if configured:
        return Path(configured).expanduser().resolve()
    return PROJECT_DIR / "front" / "dist"


FRONTEND_DIST = _frontend_dist()


def _default_data_dir() -> Path:
    configured = os.getenv("VIGIAPET_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return BACK_DIR / "app-data"


DATA_DIR = _default_data_dir()
DATABASE_PATH = DATA_DIR / "vigiapet.sqlite3"
LEGACY_DATABASE_PATHS = (DATA_DIR / "monitorapet.sqlite3",)
MODEL_DIR = DATA_DIR / "models"
MODEL_PATH = MODEL_DIR / "yolox_tiny.onnx"
PET_EMBEDDING_MODEL_PATH = MODEL_DIR / "mobilenetv2_embedding.onnx"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
CLIP_DIR = DATA_DIR / "clips"
PET_IMAGE_DIR = DATA_DIR / "pets"


def ensure_data_directories() -> None:
    for directory in (DATA_DIR, SNAPSHOT_DIR, CLIP_DIR, PET_IMAGE_DIR, DATA_DIR / "logs", MODEL_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_database()


def _migrate_legacy_database() -> None:
    """Renomeia o banco de versões anteriores (nome antigo do projeto) uma única vez."""
    if DATABASE_PATH.exists():
        return
    for legacy in LEGACY_DATABASE_PATHS:
        if legacy.exists():
            legacy.rename(DATABASE_PATH)
            return
