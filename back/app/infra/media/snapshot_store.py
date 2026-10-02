from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import DATA_DIR, SNAPSHOT_DIR


class SnapshotStore:
    def save(self, content: bytes | None, captured_at: datetime) -> str | None:
        if not content:
            return None
        directory = SNAPSHOT_DIR / captured_at.strftime("%Y/%m/%d")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid4()}.jpg"
        path.write_bytes(content)
        return path.relative_to(DATA_DIR).as_posix()

    def resolve(self, relative_path: str) -> Path:
        path = (DATA_DIR / relative_path).resolve()
        if DATA_DIR.resolve() not in path.parents:
            raise ValueError("Caminho de snapshot inválido.")
        return path
