from datetime import datetime
from decimal import Decimal

from app.adapters.values import (
    epoch_seconds,
    format_datetime,
    parse_datetime,
    parse_decimal,
)


def test_parse_datetime_accepts_epoch_seconds_and_millis() -> None:
    assert parse_datetime(0) == datetime(1970, 1, 1, 8)
    assert parse_datetime(0) == parse_datetime(0_000)


def test_parse_datetime_accepts_strings() -> None:
    assert parse_datetime("2026-10-27 12:00:00") == datetime(2026, 10, 27, 12)
    assert parse_datetime("2026-10-27") == datetime(2026, 10, 27)


def test_parse_datetime_rejects_blank() -> None:
    assert parse_datetime(None) is None
    assert parse_datetime("") is None


def test_parse_decimal_strips_currency_and_commas() -> None:
    assert parse_decimal("￥1,234.50") == Decimal("1234.50")
    assert parse_decimal("") is None
    assert parse_decimal("bad") is None


def test_format_and_epoch_round_trip() -> None:
    dt = datetime(2026, 10, 27, 12, 30)
    assert format_datetime(dt) == "2026-10-27 12:30:00"
    assert epoch_seconds(dt) == 1793075400
