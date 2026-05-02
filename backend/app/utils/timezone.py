from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


MANAUS_TZ = ZoneInfo("America/Manaus")


def now_manaus() -> datetime:
    return datetime.now(MANAUS_TZ)


def now_manaus_naive() -> datetime:
    return now_manaus().replace(tzinfo=None)


def today_manaus() -> date:
    return now_manaus().date()
