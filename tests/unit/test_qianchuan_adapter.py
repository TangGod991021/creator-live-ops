from datetime import datetime

import pytest

from app.adapters.base import TimeWindow
from app.adapters.qianchuan.adapter import QianchuanAdapter, parse_advertiser_pairs


class FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    async def request_with_retry(self, path: str, params: dict) -> dict:
        self.calls.append((path, params))
        return self.responses.pop(0)


WINDOW = TimeWindow(datetime(2026, 10, 26), datetime(2026, 10, 27))


def test_parse_advertiser_pairs() -> None:
    assert parse_advertiser_pairs("1:2, 3:4") == [("1", "2"), ("3", "4")]


def test_parse_advertiser_pairs_rejects_bad_value() -> None:
    with pytest.raises(ValueError, match="advertiser:aweme"):
        parse_advertiser_pairs("1:2,bad")


async def test_fetch_ad_cost_paginates_and_maps() -> None:
    page_one = {
        "list": [
            {"stat_datetime": "2026-10-26 00:00:00", "stat_cost": "12.50"},
        ],
        "page_info": {"total_page": 2},
    }
    page_two = {
        "list": [
            {"stat_datetime": "2026-10-26 00:00:00", "stat_cost": "7.50"},
        ],
        "page_info": {"total_page": 2},
    }
    client = FakeClient([page_one, page_two])
    adapter = QianchuanAdapter(client, [("100", "200")])

    rows = await adapter.fetch_ad_cost(WINDOW)

    assert len(rows) == 2
    assert rows[0]["account_id"] == "100"
    assert rows[0]["granularity"] == "day"
    assert str(rows[0]["cost"]) == "12.50"
    assert rows[0]["stat_time"] == datetime(2026, 10, 26)
    assert client.calls[0][1]["advertiser_id"] == "100"
    assert client.calls[0][1]["aweme_id"] == "200"
    assert client.calls[0][1]["dimension"] == "TIME_GRANULARITY_DAILY"
    assert client.calls[0][1]["page"] == 1
    assert client.calls[1][1]["page"] == 2


async def test_rows_without_stat_datetime_are_skipped() -> None:
    client = FakeClient(
        [{"list": [{"stat_cost": "1.00"}], "page_info": {"total_page": 1}}]
    )
    adapter = QianchuanAdapter(client, [("1", "2")])
    assert await adapter.fetch_ad_cost(WINDOW) == []
