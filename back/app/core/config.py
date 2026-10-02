from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "MonitoraPet"
APP_VERSION = "0.2.0"
BACK_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACK_DIR.parent
FRONTEND_DIST = PROJECT_DIR / "front" / "dist"


def _default_data_dir() -> Path:
    configured = os.getenv("MONITORAPET_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return BACK_DIR / "app-data"


DATA_DIR = _default_data_dir()
DATABASE_PATH = DATA_DIR / "monitorapet.sqlite3"
MODEL_DIR = DATA_DIR / "models"
MODEL_PATH = MODEL_DIR / "yolox_tiny.onnx"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
CLIP_DIR = DATA_DIR / "clips"


def ensure_data_directories() -> None:
    for directory in (DATA_DIR, SNAPSHOT_DIR, CLIP_DIR, DATA_DIR / "logs", MODEL_DIR):
        directory.mkdir(parents=True, exist_ok=True)
