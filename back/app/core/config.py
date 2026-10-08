from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "Monitora Pet"
APP_VERSION = "0.3.2"
BACK_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACK_DIR.parent
DATABASE_FILENAME = "monitorapet.sqlite3"
# O banco ja se chamou assim; migrate_legacy_database renomeia na subida.
LEGACY_DATABASE_FILENAMES = ("vigiapet.sqlite3",)


def env(name: str, default: str = "") -> str:
    """Le MONITORAPET_<name>, caindo para o VIGIAPET_<name> antigo.

    O projeto ja usou o prefixo VIGIAPET_; o fallback existe para que um
    ambiente configurado antes do rename continue funcionando.
    """
    return os.getenv(f"MONITORAPET_{name}") or os.getenv(f"VIGIAPET_{name}") or default


def _path_from_env(name: str, default: Path) -> Path:
    configured = env(name)
    return Path(configured).expanduser().resolve() if configured else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    frontend_dist: Path

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            data_dir=_path_from_env("DATA_DIR", BACK_DIR / "app-data"),
            frontend_dist=_path_from_env("FRONTEND_DIST", PROJECT_DIR / "front" / "dist"),
        )

    @property
    def database_path(self) -> Path:
        return self.data_dir / DATABASE_FILENAME

    @property
    def model_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def model_path(self) -> Path:
        return self.model_dir / "yolox_tiny.onnx"

    @property
    def embedding_model_path(self) -> Path:
        return self.model_dir / "mobilenetv2_embedding.onnx"

    @property
    def snapshot_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def clip_dir(self) -> Path:
        return self.data_dir / "clips"

    @property
    def pet_image_dir(self) -> Path:
        return self.data_dir / "pets"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def recordings_dir(self) -> Path:
        return self.data_dir / "recordings"

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir, self.snapshot_dir, self.clip_dir, self.pet_image_dir, self.log_dir, self.model_dir,
            self.recordings_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self.migrate_legacy_database()

    def migrate_legacy_database(self) -> None:
        if self.database_path.exists():
            return
        for filename in LEGACY_DATABASE_FILENAMES:
            legacy = self.data_dir / filename
            if legacy.exists():
                legacy.rename(self.database_path)
                return


SETTINGS = Settings.from_env()
DATA_DIR = SETTINGS.data_dir
FRONTEND_DIST = SETTINGS.frontend_dist
DATABASE_PATH = SETTINGS.database_path
MODEL_DIR = SETTINGS.model_dir
MODEL_PATH = SETTINGS.model_path
PET_EMBEDDING_MODEL_PATH = SETTINGS.embedding_model_path
SNAPSHOT_DIR = SETTINGS.snapshot_dir
CLIP_DIR = SETTINGS.clip_dir
PET_IMAGE_DIR = SETTINGS.pet_image_dir


def ensure_data_directories() -> None:
    SETTINGS.ensure_directories()
