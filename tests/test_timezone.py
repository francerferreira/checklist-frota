from __future__ import annotations

from datetime import timedelta
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.timezone import MANAUS_TZ, now_manaus, now_manaus_naive, today_manaus  # noqa: E402


def test_manaus_timezone_uses_utc_minus_four():
    current = now_manaus()

    assert current.tzinfo is MANAUS_TZ
    assert current.utcoffset() == timedelta(hours=-4)


def test_manaus_naive_datetime_keeps_local_clock_without_timezone_marker():
    current = now_manaus()
    naive = now_manaus_naive()

    assert naive.tzinfo is None
    assert abs(naive - current.replace(tzinfo=None)) < timedelta(seconds=5)


def test_today_manaus_uses_manaus_calendar_day():
    assert today_manaus() == now_manaus().date()
