import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.adapters.base import (
    AuthError,
    PermanentError,
    RateLimitError,
    RetryableError,
    UnsupportedResource,
)
from app.scheduler.models import RetryPolicy


@dataclass(frozen=True)
class AttemptedResult[T]:
    value: T
    attempts: int


async def retry_call[T](
    call: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AttemptedResult[T]:
    max_attempts = max(1, policy.max_attempts)
    for attempt in range(1, max_attempts + 1):
        try:
            return AttemptedResult(await call(), attempt)
        except (AuthError, PermanentError, UnsupportedResource):
            raise
        except RetryableError as exc:
            if attempt >= max_attempts:
                raise
            if isinstance(exc, RateLimitError) and exc.retry_after is not None:
                delay = exc.retry_after
            else:
                delay = policy.backoff_seconds * (2 ** (attempt - 1))
            await sleep(float(delay))
    raise AssertionError("unreachable")
