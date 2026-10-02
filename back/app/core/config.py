from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "MonitoraPet"
APP_VERSION = "0.1.0"
BACK_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACK_DIR.parent
FRONTEND_DIST = PROJECT_DIR / "front" / "dist"


def _default_data_dir() -> Path:
    configured = os.getenv("MONITORAPET_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return BACK_DIR / "app-data"


DATA_DIR = _default_data_dir()
DATABASE_PATH = DATA_DIR / "monitorapet.sqlite3"


def ensure_data_directories() -> None:
    for directory in (DATA_DIR, DATA_DIR / "snapshots", DATA_DIR / "clips", DATA_DIR / "logs"):
        directory.mkdir(parents=True, exist_ok=True)
