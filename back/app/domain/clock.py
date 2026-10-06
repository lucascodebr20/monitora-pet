from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from time import monotonic
from typing import Protocol


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_today() -> date:
    return datetime.now().astimezone().date()


def utc_bounds_for_local_date(value: str) -> tuple[str, str]:
    local_timezone = datetime.now().astimezone().tzinfo
    local_start = datetime.combine(date.fromisoformat(value), time.min, tzinfo=local_timezone)
    local_end = local_start + timedelta(days=1)
    return (
        local_start.astimezone(timezone.utc).isoformat(),
        local_end.astimezone(timezone.utc).isoformat(),
    )


@dataclass(frozen=True)
class Moment:
    monotonic: float
    utc: datetime


class Clock(Protocol):
    def now(self) -> Moment: ...


class SystemClock:
    def now(self) -> Moment:
        return Moment(monotonic(), datetime.now(timezone.utc))
