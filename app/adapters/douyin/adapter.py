from typing import Any

from app.adapters.base import AuthError, BaseAdapter, TimeWindow, UnsupportedResource
from app.adapters.douyin.client import DouyinClient
from app.adapters.douyin.token import DouyinTokenProvider
from app.adapters.values import (
    epoch_seconds,
    format_datetime,
    parse_datetime,
    parse_decimal,
)

MAX_PAGES = 1000


class DouyinShopAdapter(BaseAdapter):
    platform = "douyin"
    lane = "douyin_shop"

    def __init__(
        self,
        client: DouyinClient,
        token_provider: DouyinTokenProvider | None = None,
        *,
        page_size: int = 50,
    ) -> None:
        self._client = client
        self._token_provider = token_provider
        self._page_size = page_size

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self._client.request_with_retry(method, params)
        except AuthError:
            if self._token_provider is None:
                raise
            token = await self._token_provider.refresh()
            self._client.access_token = token
            return await self._client.request_with_retry(method, params)

    async def fetch_orders(self, window: TimeWindow) -> list[dict[str, Any]]:
        created = await self._list_orders(window, "create")
        updated = await self._list_orders(window, "update")
        merged = {row["order_id"]: row for row in created}
        merged.update({row["order_id"]: row for row in updated})
        return list(merged.values())

    async def _list_orders(
        self, window: TimeWindow, time_type: str
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 0
        collected = 0
        while page < MAX_PAGES:
            params: dict[str, Any] = {"page": page, "size": self._page_size}
            if time_type == "update":
                params["update_time_start"] = epoch_seconds(window.start_at)
                params["update_time_end"] = epoch_seconds(window.end_at) - 1
            else:
                params["create_time_start"] = epoch_seconds(window.start_at)
                params["create_time_end"] = epoch_seconds(window.end_at) - 1
            data = await self._request("order.searchList", params)
            items = data.get("shop_order_list") or []
            for item in items:
                normalized = self._normalize_order(item)
                if normalized is not None:
                    rows.append(normalized)
            collected += len(items)
            total = int(data.get("total") or 0)
            page += 1
            if not items or collected >= total:
                break
        return rows

    @staticmethod
    def _normalize_order(item: dict[str, Any]) -> dict[str, Any] | None:
        payload = item.get("shop_order_detail")
        detail = payload if isinstance(payload, dict) else item
        order_id = detail.get("order_id") or detail.get("shop_order_id")
        if not order_id:
            return None
        return {
            "order_id": str(order_id),
            "shop_id": _string(detail.get("shop_id")),
            "order_status": _string(
                detail.get("order_status") or detail.get("order_status_desc")
            ),
            "pay_amount": parse_decimal(
                detail.get("pay_amount") or detail.get("pay_amount_str")
            ),
            "pay_at": parse_datetime(
                detail.get("pay_time") or detail.get("pay_time_str")
            ),
            "create_at": parse_datetime(
                detail.get("create_time") or detail.get("create_time_str")
            ),
            "update_at": parse_datetime(
                detail.get("update_time") or detail.get("update_time_str")
            ),
            "talent_id": _string(detail.get("talent_id") or detail.get("author_id")),
            "room_id": _string(detail.get("room_id_str") or detail.get("room_id")),
            "channel_type": _string(
                detail.get("channel_type") or detail.get("order_channel")
            ),
            "content_type": _string(
                detail.get("content_type") or detail.get("product_type")
            ),
            "raw_json": item,
        }

    async def fetch_after_sales(self, window: TimeWindow) -> list[dict[str, Any]]:
        created = await self._list_after_sales(window, "create")
        updated = await self._list_after_sales(window, "update")
        merged = {row["after_sale_id"]: row for row in created}
        merged.update({row["after_sale_id"]: row for row in updated})
        return list(merged.values())

    async def _list_after_sales(
        self, window: TimeWindow, time_type: str
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 0
        collected = 0
        while page < MAX_PAGES:
            params: dict[str, Any] = {"page": page, "size": self._page_size}
            if time_type == "update":
                params["order_by"] = ["update_time desc"]
                params["update_start_time"] = epoch_seconds(window.start_at)
                params["update_end_time"] = epoch_seconds(window.end_at) - 1
            else:
                params["start_time"] = epoch_seconds(window.start_at)
                params["end_time"] = epoch_seconds(window.end_at) - 1
            data = await self._request("afterSale.List", params)
            items = data.get("items") or []
            for item in items:
                normalized = self._normalize_after_sale(item)
                if normalized is not None:
                    rows.append(normalized)
            collected += len(items)
            total = int(data.get("total") or 0)
            page += 1
            if not items or collected >= total:
                break
        return rows

    @staticmethod
    def _normalize_after_sale(item: dict[str, Any]) -> dict[str, Any] | None:
        info = item.get("aftersale_info")
        info = info if isinstance(info, dict) else {}
        order_info = item.get("order_info")
        order_info = order_info if isinstance(order_info, dict) else {}
        after_sale_id = info.get("aftersale_id")
        if not after_sale_id:
            return None
        return {
            "after_sale_id": str(after_sale_id),
            "order_id": _string(
                order_info.get("shop_order_id") or info.get("order_id")
            ),
            "type": _string(info.get("aftersale_type") or info.get("type")),
            "status": _string(info.get("aftersale_status") or info.get("status")),
            "refund_amount": parse_decimal(info.get("refund_amount")),
            "apply_at": parse_datetime(info.get("apply_time")),
            "finish_at": parse_datetime(
                info.get("refund_time") or info.get("finish_time")
            ),
            "update_at": parse_datetime(info.get("update_time")),
            "raw_json": item,
        }

    async def fetch_settlements(self, window: TimeWindow) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        params: dict[str, Any] = {
            "start_time": format_datetime(window.start_at),
            "end_time": format_datetime(window.end_at),
            "time_type": 0,
            "size": 100,
            "start_index": "",
        }
        for _ in range(MAX_PAGES):
            data = await self._request("order.getSettleBillDetailV3", params)
            for record in data.get("data") or []:
                normalized = self._normalize_settlement(record)
                if normalized is not None:
                    rows.append(normalized)
            if int(data.get("is_end", 1)) == 1:
                break
            next_index = str(data.get("next_start_index") or "").strip()
            next_time = data.get("next_start_time") or ""
            if not next_index and not next_time:
                break
            params["start_index"] = next_index
            if next_time:
                params["start_time"] = str(next_time)
        return rows

    @staticmethod
    def _normalize_settlement(record: dict[str, Any]) -> dict[str, Any] | None:
        settlement_id = (
            record.get("request_no")
            or record.get("settle_id")
            or record.get("settlement_id")
        )
        if not settlement_id:
            return None
        return {
            "settlement_id": str(settlement_id),
            "order_id": _string(
                record.get("shop_order_id") or record.get("order_id")
            ),
            "settle_at": parse_datetime(
                record.get("settle_time") or record.get("finish_time")
            ),
            "settle_amount": parse_decimal(
                record.get("settle_amount") or record.get("order_settle_amount")
            ),
            "commission_amount": parse_decimal(record.get("commission_amount")),
            "talent_commission": parse_decimal(record.get("talent_commission")),
            "service_fee": parse_decimal(record.get("service_fee")),
            "platform_fee": parse_decimal(record.get("platform_fee")),
            "raw_json": record,
        }

    async def fetch_live_rooms(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(
            "douyin shop api does not expose live room sessions; use csv_import"
        )

    async def fetch_ad_cost(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource("douyin shop adapter does not support ad cost")

    async def close(self) -> None:
        await self._client.close()


def _string(value: object) -> str:
    return "" if value is None else str(value)
