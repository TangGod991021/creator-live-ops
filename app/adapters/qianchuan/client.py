from typing import Any

import httpx

from app.adapters.base import AuthError, PermanentError, RateLimitError, TransientError
from app.adapters.retry import retry_call
from app.scheduler.models import RetryPolicy

DEFAULT_RETRY = RetryPolicy(max_attempts=3, backoff_seconds=1)
PERMANENT_CODES = {40000}
RETRYABLE_CODES = {400153}


class QianchuanClient:
    def __init__(
        self,
        *,
        access_token: str,
        base_url: str = "https://api.oceanengine.com/open_api",
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limit_delay: float = 10.0,
    ) -> None:
        self._retry_policy = retry_policy or DEFAULT_RETRY
        self._rate_limit_delay = rate_limit_delay
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            transport=transport,
            headers={
                "Access-Token": access_token,
                "Content-Type": "application/json;charset=utf-8",
            },
        )

    async def request(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await self._client.get(path.lstrip("/"), params=params)
        if response.status_code == 515:
            raise RateLimitError(
                "qianchuan rate limited", retry_after=self._rate_limit_delay
            )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "qianchuan rate limited",
                retry_after=(
                    float(retry_after) if retry_after else self._rate_limit_delay
                ),
            )
        if response.status_code in {401, 403}:
            raise AuthError(f"qianchuan auth failed: HTTP {response.status_code}")
        if response.status_code >= 500:
            raise TransientError(
                f"qianchuan server error: HTTP {response.status_code}"
            )
        if response.status_code != 200:
            raise PermanentError(
                f"qianchuan request failed: HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise TransientError("qianchuan returned invalid JSON") from exc

        code = payload.get("code")
        if code == 0:
            data = payload.get("data")
            return data if isinstance(data, dict) else {}
        message = payload.get("message") or "unknown error"
        if code in PERMANENT_CODES:
            raise PermanentError(f"qianchuan api error code={code}: {message}")
        if code in RETRYABLE_CODES:
            raise TransientError(f"qianchuan api error code={code}: {message}")
        raise PermanentError(f"qianchuan api error code={code}: {message}")

    async def request_with_retry(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        result = await retry_call(
            lambda: self.request(path, params), self._retry_policy
        )
        return result.value

    async def close(self) -> None:
        await self._client.aclose()
