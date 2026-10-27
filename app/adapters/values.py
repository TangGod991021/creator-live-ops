from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Asia/Shanghai")


def parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, TIMEZONE).replace(tzinfo=None)
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(TIMEZONE).replace(tzinfo=None)
    return parsed


def parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("￥", "").replace("¥", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def epoch_seconds(value: datetime) -> int:
    aware = value.replace(tzinfo=TIMEZONE) if value.tzinfo is None else value
    return int(aware.timestamp())
