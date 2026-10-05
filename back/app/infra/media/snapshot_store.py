from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import DATA_DIR, SNAPSHOT_DIR


class SnapshotStore:
    def __init__(self, data_dir: Path = DATA_DIR, snapshot_dir: Path = SNAPSHOT_DIR) -> None:
        self.data_dir = data_dir
        self.snapshot_dir = snapshot_dir

    def save(self, content: bytes | None, captured_at: datetime) -> str | None:
        if not content:
            return None
        directory = self.snapshot_dir / captured_at.strftime("%Y/%m/%d")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid4()}.jpg"
        path.write_bytes(content)
        return path.relative_to(self.data_dir).as_posix()

    def resolve(self, relative_path: str) -> Path:
        path = (self.data_dir / relative_path).resolve()
        if self.data_dir.resolve() not in path.parents:
            raise ValueError("Caminho de snapshot inválido.")
        return path
