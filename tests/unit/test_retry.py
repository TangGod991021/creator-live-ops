import pytest

from app.adapters.base import AuthError, PermanentError, RateLimitError, TransientError
from app.adapters.retry import retry_call
from app.scheduler.models import RetryPolicy


async def test_retry_transient_until_success() -> None:
    calls = 0
    delays: list[float] = []

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TransientError("boom")
        return "ok"

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    result = await retry_call(flaky, RetryPolicy(3, 2), sleep=fake_sleep)
    assert result.value == "ok"
    assert result.attempts == 3
    assert delays == [2, 4]


async def test_retry_does_not_retry_auth_or_permanent() -> None:
    async def auth() -> str:
        raise AuthError("bad token")

    with pytest.raises(AuthError):
        await retry_call(auth, RetryPolicy(3, 1), sleep=_noop)

    async def permanent() -> str:
        raise PermanentError("bad params")

    with pytest.raises(PermanentError):
        await retry_call(permanent, RetryPolicy(3, 1), sleep=_noop)


async def test_retry_honours_rate_limit_delay() -> None:
    delays: list[float] = []
    calls = 0

    async def limited() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RateLimitError("slow down", retry_after=7)
        return "ok"

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    result = await retry_call(limited, RetryPolicy(2, 30), sleep=fake_sleep)
    assert result.value == "ok"
    assert delays == [7]


async def _noop(seconds: float) -> None:
    return None
