from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


class AdapterError(Exception):
    pass


class UnsupportedResource(AdapterError):
    pass


class AuthError(AdapterError):
    pass


class PermanentError(AdapterError):
    pass


class RetryableError(AdapterError):
    pass


class TransientError(RetryableError):
    pass


class RateLimitError(RetryableError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class TimeWindow:
    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        if self.start_at >= self.end_at:
            raise ValueError("start_at must be before end_at")

    def iter_slices(self, minutes: int) -> Iterator["TimeWindow"]:
        if minutes <= 0:
            raise ValueError("minutes must be positive")
        cursor = self.start_at
        while cursor < self.end_at:
            next_cursor = min(cursor + timedelta(minutes=minutes), self.end_at)
            yield TimeWindow(cursor, next_cursor)
            cursor = next_cursor


class BaseAdapter:
    platform: str = ""
    lane: str = ""

    async def fetch_orders(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support orders")

    async def fetch_after_sales(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support after sales")

    async def fetch_settlements(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support settlements")

    async def fetch_live_rooms(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support live rooms")

    async def fetch_ad_cost(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support ad cost")

    async def close(self) -> None:
        return None
