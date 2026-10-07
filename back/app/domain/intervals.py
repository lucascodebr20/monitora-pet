from __future__ import annotations

from datetime import datetime

Interval = tuple[datetime, datetime]


def subtract_intervals(start: datetime, end: datetime, covered: list[Interval]) -> list[Interval]:
    windows: list[Interval] = []
    cursor = start
    for covered_start, covered_end in sorted(covered):
        if covered_end <= cursor:
            continue
        if covered_start >= end:
            break
        if covered_start > cursor:
            windows.append((cursor, covered_start))
        cursor = max(cursor, covered_end)
    if cursor < end:
        windows.append((cursor, end))
    return windows


def contains(windows: list[Interval], moment: datetime) -> bool:
    return any(start <= moment < end for start, end in windows)
