import hashlib
import hmac
import json
from typing import Any


def canonical_json(params: dict[str, Any]) -> str:
    return json.dumps(
        params,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sign_request(
    *,
    app_key: str,
    app_secret: str,
    method: str,
    param_json: str,
    timestamp: str,
    version: str = "2",
) -> str:
    sign_base = (
        f"{app_secret}"
        f"app_key{app_key}"
        f"method{method}"
        f"param_json{param_json}"
        f"timestamp{timestamp}"
        f"v{version}"
        f"{app_secret}"
    )
    return hmac.new(
        app_secret.encode("utf-8"),
        sign_base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().lower()
