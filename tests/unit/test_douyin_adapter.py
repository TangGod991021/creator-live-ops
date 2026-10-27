from datetime import datetime

import pytest

from app.adapters.base import TimeWindow, UnsupportedResource
from app.adapters.douyin.adapter import DouyinShopAdapter


class FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []
        self.access_token = "token"

    async def request_with_retry(self, method: str, params: dict | None = None) -> dict:
        self.calls.append((method, params or {}))
        return self.responses.pop(0)


WINDOW = TimeWindow(datetime(2026, 10, 26), datetime(2026, 10, 27))


async def test_orders_merge_created_and_updated_passes() -> None:
    created = {
        "total": 2,
        "shop_order_list": [
            {
                "order_id": "o1",
                "pay_amount": "10.00",
                "pay_time": "2026-10-26 10:00:00",
            },
            {
                "order_id": "o2",
                "pay_amount": "20.00",
                "pay_time": "2026-10-26 11:00:00",
            },
        ],
    }
    updated = {
        "total": 1,
        "shop_order_list": [
            {
                "order_id": "o1",
                "pay_amount": "12.00",
                "pay_time": "2026-10-26 10:00:00",
                "order_status": "paid",
            },
        ],
    }
    client = FakeClient([created, updated])
    adapter = DouyinShopAdapter(client)

    rows = await adapter.fetch_orders(WINDOW)

    assert len(rows) == 2
    assert {row["order_id"] for row in rows} == {"o1", "o2"}
    first = next(row for row in rows if row["order_id"] == "o1")
    assert str(first["pay_amount"]) == "12.00"
    assert first["order_status"] == "paid"
    assert first["raw_json"]["order_id"] == "o1"
    assert client.calls[0][1]["create_time_start"] == 1792944000
    assert client.calls[1][1]["update_time_start"] == 1792944000


async def test_after_sales_maps_nested_payload() -> None:
    response = {
        "total": 1,
        "items": [
            {
                "aftersale_info": {
                    "aftersale_id": 9001,
                    "aftersale_type": "refund",
                    "aftersale_status": "success",
                    "refund_amount": "8.88",
                    "apply_time": "2026-10-26 09:00:00",
                    "refund_time": "2026-10-26 12:00:00",
                    "update_time": "2026-10-26 12:00:00",
                },
                "order_info": {"shop_order_id": "o1"},
            }
        ],
    }
    adapter = DouyinShopAdapter(FakeClient([response, {"total": 0, "items": []}]))

    rows = await adapter.fetch_after_sales(WINDOW)

    assert len(rows) == 1
    row = rows[0]
    assert row["after_sale_id"] == "9001"
    assert row["order_id"] == "o1"
    assert row["type"] == "refund"
    assert row["status"] == "success"
    assert str(row["refund_amount"]) == "8.88"
    assert row["apply_at"] == datetime(2026, 10, 26, 9)
    assert row["finish_at"] == datetime(2026, 10, 26, 12)


async def test_settlements_follow_cursor_until_is_end() -> None:
    first = {
        "is_end": 0,
        "data": [
            {
                "request_no": "s1",
                "shop_order_id": "o1",
                "settle_amount": "100.00",
                "settle_time": "2026-10-26 01:00:00",
            }
        ],
        "next_start_index": "cursor-2",
        "next_start_time": "2026-10-26 02:00:00",
    }
    second = {
        "is_end": 1,
        "data": [
            {
                "request_no": "s2",
                "shop_order_id": "o2",
                "settle_amount": "50.00",
                "settle_time": "2026-10-26 03:00:00",
            }
        ],
        "next_start_index": "",
        "next_start_time": "",
    }
    client = FakeClient([first, second])
    adapter = DouyinShopAdapter(client)

    rows = await adapter.fetch_settlements(WINDOW)

    assert [row["settlement_id"] for row in rows] == ["s1", "s2"]
    assert str(rows[0]["settle_amount"]) == "100.00"
    assert client.calls[1][1]["start_index"] == "cursor-2"
    assert client.calls[1][1]["start_time"] == "2026-10-26 02:00:00"


async def test_live_rooms_are_not_supported_by_douyin_adapter() -> None:
    adapter = DouyinShopAdapter(FakeClient([]))
    with pytest.raises(UnsupportedResource, match="live room"):
        await adapter.fetch_live_rooms(WINDOW)
