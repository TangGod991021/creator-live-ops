import httpx
import pytest

from app.adapters.base import AuthError, PermanentError
from app.adapters.douyin.client import DouyinClient
from app.adapters.douyin.signer import sign_request
from app.scheduler.models import RetryPolicy


def make_client(handler, *, token: str = "token") -> DouyinClient:
    return DouyinClient(
        app_key="test_key",
        app_secret="test_secret",
        access_token=token,
        transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
    )


async def test_request_builds_signed_query_and_returns_data() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"code": 0, "data": {"ok": True}})

    client = make_client(handler)
    data = await client.request("order.searchList", {"size": 50, "page": 0})
    assert data == {"ok": True}

    request = captured[0]
    assert request.url.path == "/order/searchList"
    assert request.url.params["method"] == "order.searchList"
    assert request.url.params["app_key"] == "test_key"
    assert request.url.params["access_token"] == "token"
    assert request.url.params["sign_method"] == "hmac-sha256"
    param_json = request.content.decode("utf-8")
    assert param_json == '{"page":0,"size":50}'
    expected_sign = sign_request(
        app_key="test_key",
        app_secret="test_secret",
        method="order.searchList",
        param_json=param_json,
        timestamp=request.url.params["timestamp"],
    )
    assert request.url.params["sign"] == expected_sign


async def test_token_endpoint_omits_access_token() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"code": 10000, "data": {"access_token": "new"}})

    client = make_client(handler)
    data = await client.request(
        "token.create",
        {"code": "", "grant_type": "authorization_self"},
        include_access_token=False,
    )
    assert data == {"access_token": "new"}
    assert "access_token" not in captured[0].url.params


async def test_transient_http_error_is_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"code": 0, "data": {"ok": True}})

    client = make_client(handler)
    assert await client.request_with_retry("order.searchList", {}) == {"ok": True}
    assert calls == 2


async def test_business_error_is_permanent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 10001, "msg": "param error"})

    client = make_client(handler)
    with pytest.raises(PermanentError, match="10001"):
        await client.request("order.searchList", {})


async def test_http_401_is_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = make_client(handler)
    with pytest.raises(AuthError):
        await client.request("order.searchList", {})


async def test_missing_token_raises_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": {}})

    client = make_client(handler, token="")
    with pytest.raises(AuthError, match="access token"):
        await client.request("order.searchList", {})
