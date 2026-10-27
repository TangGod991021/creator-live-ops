import json
from typing import Any

from app.adapters.base import BaseAdapter, TimeWindow
from app.adapters.qianchuan.client import QianchuanClient
from app.adapters.values import format_datetime, parse_datetime, parse_decimal

REPORT_PATH = "v1.0/qianchuan/report/uni_promotion/dimension_data/author/get/"
MAX_PAGES = 1000


def parse_advertiser_pairs(value: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for chunk in value.split(","):
        item = chunk.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError("advertiser pairs must use advertiser:aweme format")
        advertiser_id, aweme_id = (part.strip() for part in item.split(":", 1))
        if not advertiser_id or not aweme_id:
            raise ValueError("advertiser pairs must use advertiser:aweme format")
        pairs.append((advertiser_id, aweme_id))
    return pairs


class QianchuanAdapter(BaseAdapter):
    platform = "douyin"
    lane = "douyin_qianchuan"

    def __init__(
        self,
        client: QianchuanClient,
        advertiser_pairs: list[tuple[str, str]],
        *,
        page_size: int = 100,
    ) -> None:
        self._client = client
        self._advertiser_pairs = advertiser_pairs
        self._page_size = page_size

    async def fetch_ad_cost(self, window: TimeWindow) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for advertiser_id, aweme_id in self._advertiser_pairs:
            page = 1
            for _ in range(MAX_PAGES):
                params: dict[str, Any] = {
                    "advertiser_id": advertiser_id,
                    "aweme_id": aweme_id,
                    "start_time": format_datetime(window.start_at),
                    "end_time": format_datetime(window.end_at),
                    "metrics": json.dumps(["stat_cost"], separators=(",", ":")),
                    "dimension": "TIME_GRANULARITY_DAILY",
                    "page": page,
                    "page_size": self._page_size,
                }
                data = await self._client.request_with_retry(REPORT_PATH, params)
                items = data.get("list") or []
                for item in items:
                    normalized = self._normalize(advertiser_id, item)
                    if normalized is not None:
                        rows.append(normalized)
                page_info = data.get("page_info")
                total_page = int((page_info or {}).get("total_page") or 1)
                if not items or page >= total_page:
                    break
                page += 1
        return rows

    @staticmethod
    def _normalize(
        advertiser_id: str, item: dict[str, Any]
    ) -> dict[str, Any] | None:
        stat_time = parse_datetime(item.get("stat_datetime"))
        if stat_time is None:
            return None
        return {
            "account_id": advertiser_id,
            "stat_time": stat_time,
            "granularity": "day",
            "cost": parse_decimal(item.get("stat_cost")),
            "impressions": _int_or_none(item.get("impressions")),
            "clicks": _int_or_none(item.get("clicks")),
            "conversions": _int_or_none(item.get("conversions")),
            "raw_json": item,
        }

    async def close(self) -> None:
        await self._client.close()


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None
