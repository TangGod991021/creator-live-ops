from datetime import datetime

import pytest

from app.scheduler.service import default_window


def test_day_window() -> None:
    start, end = default_window("day", now=datetime(2026, 10, 26, 15, 30))
    assert start == datetime(2026, 10, 25)
    assert end == datetime(2026, 10, 26)


def test_hour_window() -> None:
    start, end = default_window("hour", now=datetime(2026, 10, 26, 15, 30))
    assert start == datetime(2026, 10, 26, 14)
    assert end == datetime(2026, 10, 26, 15)


def test_minute_window() -> None:
    start, end = default_window("minute", now=datetime(2026, 10, 26, 15, 30, 45))
    assert start == datetime(2026, 10, 26, 15, 29)
    assert end == datetime(2026, 10, 26, 15, 30)


def test_unknown_window_raises() -> None:
    with pytest.raises(ValueError, match="unsupported window"):
        default_window("week", now=datetime(2026, 10, 26))
