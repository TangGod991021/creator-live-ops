from datetime import datetime
from pathlib import Path

from app.adapters.base import TimeWindow
from app.adapters.csv.adapter import CsvImportAdapter

WINDOW = TimeWindow(datetime(2026, 10, 26), datetime(2026, 10, 27))
MAPPINGS = Path("app/adapters/csv/mappings")


def write_csv(tmp_path: Path, dataset: str, name: str, content: str) -> None:
    directory = tmp_path / dataset
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(content, encoding="utf-8-sig")


async def test_orders_filter_window_and_dedupe(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "orders",
        "orders.csv",
        "订单编号,实付金额,支付时间\n"
        "o1,10.00,2026-10-26 10:00:00\n"
        "o2,20.00,2026-10-25 10:00:00\n"
        "o1,15.00,2026-10-26 11:00:00\n",
    )
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    rows = await adapter.fetch_orders(WINDOW)
    assert len(rows) == 1
    assert rows[0]["order_id"] == "o1"
    assert str(rows[0]["pay_amount"]) == "15.00"
    assert rows[0]["raw_json"]["订单编号"] == "o1"


async def test_live_rooms_do_not_filter_by_window(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "live_rooms",
        "rooms.csv",
        "直播间ID,店铺ID,开播时间,下播时间\n"
        "r1,s1,2026-12-01 20:00:00,2026-12-01 23:00:00\n",
    )
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    rows = await adapter.fetch_live_rooms(WINDOW)
    assert len(rows) == 1
    assert rows[0]["room_id"] == "r1"
    assert rows[0]["start_at"] == datetime(2026, 12, 1, 20)


async def test_invalid_decimal_row_is_skipped(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "orders",
        "orders.csv",
        "订单编号,实付金额,支付时间\n"
        "o1,bad,2026-10-26 10:00:00\n"
        "o2,20.00,2026-10-26 11:00:00\n",
    )
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    rows = await adapter.fetch_orders(WINDOW)
    assert [row["order_id"] for row in rows] == ["o2"]
    assert adapter.errors


async def test_missing_required_column_is_skipped_by_default(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "orders",
        "orders.csv",
        "订单编号,实付金额,支付时间\n"
        ",10.00,2026-10-26 10:00:00\n",
    )
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    rows = await adapter.fetch_orders(WINDOW)
    assert rows == []
    assert adapter.errors


async def test_missing_directory_returns_empty(tmp_path: Path) -> None:
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    assert await adapter.fetch_orders(WINDOW) == []
