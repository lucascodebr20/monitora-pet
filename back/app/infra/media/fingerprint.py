from __future__ import annotations

import hashlib
from pathlib import Path

SAMPLE_BYTES = 1024 * 1024


def fingerprint_file(path: Path) -> str:
    size = path.stat().st_size
    digest = hashlib.sha256(str(size).encode("ascii"))
    with path.open("rb") as handle:
        digest.update(handle.read(SAMPLE_BYTES))
        if size > SAMPLE_BYTES:
            handle.seek(max(SAMPLE_BYTES, size - SAMPLE_BYTES))
            digest.update(handle.read(SAMPLE_BYTES))
    return digest.hexdigest()
