from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.adapters.base import AuthError, PermanentError, RateLimitError, TransientError
from app.adapters.douyin.signer import canonical_json, sign_request
from app.adapters.retry import retry_call
from app.scheduler.models import RetryPolicy

SUCCESS_CODES = {0, 10000}
DEFAULT_RETRY = RetryPolicy(max_attempts=3, backoff_seconds=1)


class DouyinClient:
    def __init__(
        self,
        *,
        app_key: str,
        app_secret: str,
        access_token: str = "",
        base_url: str = "https://openapi-fxg.jinritemai.com",
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self._retry_policy = retry_policy or DEFAULT_RETRY
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={"Content-Type": "application/json;charset=utf-8"},
        )

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        include_access_token: bool = True,
    ) -> dict[str, Any]:
        business_params = params or {}
        timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        param_json = canonical_json(business_params)
        query: dict[str, str] = {
            "method": method,
            "app_key": self.app_key,
            "timestamp": timestamp,
            "v": "2",
            "sign_method": "hmac-sha256",
            "sign": sign_request(
                app_key=self.app_key,
                app_secret=self.app_secret,
                method=method,
                param_json=param_json,
                timestamp=timestamp,
            ),
        }
        if include_access_token:
            if not self.access_token:
                raise AuthError("douyin access token is not configured")
            query["access_token"] = self.access_token

        response = await self._client.post(
            f"/{method.replace('.', '/')}",
            params=query,
            content=param_json.encode("utf-8"),
        )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "douyin rate limited",
                retry_after=float(retry_after) if retry_after else None,
            )
        if response.status_code in {401, 403}:
            raise AuthError(f"douyin auth failed: HTTP {response.status_code}")
        if response.status_code >= 500:
            raise TransientError(f"douyin server error: HTTP {response.status_code}")
        if response.status_code != 200:
            raise PermanentError(f"douyin request failed: HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise TransientError("douyin returned invalid JSON") from exc

        code = payload.get("code")
        if code in SUCCESS_CODES:
            data = payload.get("data")
            return data if isinstance(data, dict) else {}
        message = payload.get("msg") or payload.get("message") or "unknown error"
        raise PermanentError(f"douyin api error code={code}: {message}")

    async def request_with_retry(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        include_access_token: bool = True,
    ) -> dict[str, Any]:
        result = await retry_call(
            lambda: self.request(
                method,
                params,
                include_access_token=include_access_token,
            ),
            self._retry_policy,
        )
        return result.value

    async def close(self) -> None:
        await self._client.aclose()
