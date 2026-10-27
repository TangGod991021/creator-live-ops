import httpx
import pytest

from app.adapters.base import AuthError, PermanentError, RateLimitError
from app.adapters.qianchuan.client import QianchuanClient
from app.scheduler.models import RetryPolicy


def make_client(handler) -> QianchuanClient:
    return QianchuanClient(
        access_token="qc-token",
        transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
        rate_limit_delay=0,
    )


async def test_get_sends_access_token_header() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"code": 0, "data": {"list": []}})

    client = make_client(handler)
    data = await client.request(
        "v1.0/qianchuan/report/uni_promotion/data/get/", {"page": 1}
    )
    assert data == {"list": []}
    assert captured[0].headers["Access-Token"] == "qc-token"
    assert (
        captured[0].url.path
        == "/open_api/v1.0/qianchuan/report/uni_promotion/data/get/"
    )


async def test_http_515_is_rate_limited_and_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(515)
        return httpx.Response(200, json={"code": 0, "data": {"list": [1]}})

    client = make_client(handler)
    assert await client.request_with_retry("v1.0/x/", {}) == {"list": [1]}
    assert calls == 2


async def test_code_40000_is_permanent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 40000, "message": "downstream"})

    client = make_client(handler)
    with pytest.raises(PermanentError, match="40000"):
        await client.request("v1.0/x/", {})


async def test_http_403_is_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    client = make_client(handler)
    with pytest.raises(AuthError):
        await client.request("v1.0/x/", {})


async def test_rate_limit_error_carries_delay() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(515)

    client = make_client(handler)
    with pytest.raises(RateLimitError):
        await client.request("v1.0/x/", {})
