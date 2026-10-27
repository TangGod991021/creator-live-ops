from datetime import datetime

from sqlalchemy.dialects import mysql

from app.adapters.base import BaseAdapter, PermanentError, TimeWindow
from app.db.ods_models import OdsOrder
from app.ingest.service import RESOURCE_SPECS, build_upsert
from app.scheduler.models import JobDefinition, RetryPolicy


class FakeAdapter(BaseAdapter):
    platform = "douyin"
    lane = "csv_import"

    def __init__(self, rows: list[dict], fail_times: int = 0) -> None:
        self.rows = rows
        self.fail_times = fail_times
        self.calls = 0

    async def fetch_orders(self, window: TimeWindow) -> list[dict]:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise PermanentError("boom")
        return self.rows


class FakeFactory:
    def __init__(self, adapter: FakeAdapter) -> None:
        self.adapter = adapter
        self.closed = False

    async def get(self, name: str) -> BaseAdapter:
        return self.adapter

    async def close(self) -> None:
        self.closed = True


def test_resource_specs_cover_ingest_resources() -> None:
    assert set(RESOURCE_SPECS) == {
        "orders",
        "after_sales",
        "settlements",
        "live_rooms",
        "ad_cost",
    }
    assert RESOURCE_SPECS["orders"].method == "fetch_orders"


def test_build_upsert_excludes_primary_key_from_update_set() -> None:
    table = OdsOrder.__table__
    stmt = build_upsert(
        table,
        [
            {
                "platform": "douyin",
                "order_id": "o1",
                "raw_json": {},
                "batch_id": "b",
                "fetched_at": datetime(2026, 10, 27),
            }
        ],
    )
    compiled = str(stmt.compile(dialect=mysql.dialect()))
    assert "ON DUPLICATE KEY UPDATE" in compiled
    assert "platform = VALUES(platform)" not in compiled
    assert "order_id = VALUES(order_id)" not in compiled
    assert "etl_create_at = VALUES(etl_create_at)" not in compiled


def test_job_definition_defaults_to_sql_kind() -> None:
    job = JobDefinition(
        id="demo",
        lane="demo",
        schedule="0 1 * * *",
        resource="demo",
        window="day",
    )
    assert job.kind == "sql"
    assert job.adapter == ""


def test_retry_policy_defaults() -> None:
    assert RetryPolicy().max_attempts == 3
