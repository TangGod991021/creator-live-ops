from datetime import datetime

import pytest

from app.adapters.base import TimeWindow


def test_time_window_rejects_empty_range() -> None:
    with pytest.raises(ValueError, match="start_at must be before end_at"):
        TimeWindow(datetime(2026, 10, 27), datetime(2026, 10, 27))


def test_time_window_slices_cover_full_range() -> None:
    window = TimeWindow(datetime(2026, 10, 27, 0), datetime(2026, 10, 27, 3))
    slices = list(window.iter_slices(minutes=90))
    assert slices == [
        TimeWindow(datetime(2026, 10, 27, 0), datetime(2026, 10, 27, 1, 30)),
        TimeWindow(datetime(2026, 10, 27, 1, 30), datetime(2026, 10, 27, 3)),
    ]


def test_time_window_requires_positive_slice() -> None:
    window = TimeWindow(datetime(2026, 10, 27), datetime(2026, 10, 28))
    with pytest.raises(ValueError, match="minutes must be positive"):
        list(window.iter_slices(minutes=0))
