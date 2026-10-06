from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


class MediaCleanup:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir.resolve()

    def remove(self, paths: Iterable[str | Path]) -> int:
        removed = 0
        for relative in paths:
            path = (self.data_dir / relative).resolve() if not Path(relative).is_absolute() else Path(relative).resolve()
            if self.data_dir not in path.parents:
                continue
            try:
                path.unlink(missing_ok=True)
                removed += 1
            except OSError:
                logger.warning("Não foi possível remover a mídia %s", path)
        return removed

    def owns(self, path: str | Path) -> bool:
        resolved = Path(path).resolve()
        return self.data_dir in resolved.parents
