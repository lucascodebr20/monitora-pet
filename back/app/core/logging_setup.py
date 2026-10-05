"""Configuração de logs do VigiaPet.

Grava em ``<pasta de dados>/logs/vigiapet.log`` com rotação (3 arquivos de 2 MB) e espelha
no console. É o que permite diagnosticar um problema na máquina do usuário sem depurador.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 3


def configure_logging(log_dir: Path, level: int = logging.INFO) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "vigiapet.log"
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)

    if not any(getattr(handler, "_vigiapet_file", False) for handler in root.handlers):
        file_handler = RotatingFileHandler(log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler._vigiapet_file = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)

    if not any(getattr(handler, "_vigiapet_console", False) for handler in root.handlers):
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        console.setLevel(logging.WARNING)
        console._vigiapet_console = True  # type: ignore[attr-defined]
        root.addHandler(console)

    # Bibliotecas tagarelas ficam em WARNING para o arquivo não encher de ruído.
    for noisy in ("uvicorn.access", "httpx", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return log_file


def reset_logging() -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_vigiapet_file", False) or getattr(handler, "_vigiapet_console", False):
            root.removeHandler(handler)
            handler.close()
