from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".ts", ".h264", ".h265", ".264", ".265", ".webm"}

_PATTERN = re.compile(
    r"(?<!\d)(?P<year>20\d{2})[-_.]?(?P<month>\d{2})[-_.]?(?P<day>\d{2})"
    r"[T _\-]?(?P<hour>\d{2})[-_:.]?(?P<minute>\d{2})[-_:.]?(?P<second>\d{2})(?!\d)"
)


def is_video_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def start_time_from_name(path: Path) -> datetime | None:
    for match in _PATTERN.finditer(path.stem):
        try:
            local = datetime(
                int(match["year"]), int(match["month"]), int(match["day"]),
                int(match["hour"]), int(match["minute"]), int(match["second"]),
            )
        except ValueError:
            continue
        return local.astimezone().astimezone(timezone.utc)
    return None


def start_time_from_modification(path: Path, duration_seconds: float) -> datetime:
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return modified - __import__("datetime").timedelta(seconds=duration_seconds)
