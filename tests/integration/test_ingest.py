from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.adapters.base import BaseAdapter, PermanentError, TimeWindow
from app.core.settings import Settings
from app.db.models import EtlModelRun, EtlRun, EtlWatermark
from app.db.ods_models import OdsFetchLog, OdsOrder
from app.ingest.service import IngestionService
from app.scheduler.models import JobDefinition, RetryPolicy

pytestmark = pytest.mark.integration


class FakeAdapter(BaseAdapter):
    platform = "douyin"
    lane = "csv_import"

    def __init__(self, rows: list[dict], fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail

    async def fetch_orders(self, window: TimeWindow) -> list[dict]:
        if self.fail:
            raise PermanentError("fetch failed")
        return self.rows


class FakeFactory:
    def __init__(self, adapter: FakeAdapter) -> None:
        self.adapter = adapter

    async def get(self, name: str) -> BaseAdapter:
        return self.adapter

    async def close(self) -> None:
        return None


def make_job() -> JobDefinition:
    return JobDefinition(
        id="test_ingest",
        lane="csv_import",
        schedule="0 1 * * *",
        resource="orders",
        window="day",
        retry=RetryPolicy(max_attempts=1, backoff_seconds=0),
        timeout_seconds=30,
        kind="ingest",
        adapter="csv_import",
    )


def make_row(order_id: str) -> dict:
    return {
        "order_id": order_id,
        "shop_id": "s1",
        "pay_amount": "10.00",
        "pay_at": datetime(2026, 10, 26, 10),
        "raw_json": {"order_id": order_id},
    }


async def create_run(db_session, start_at, end_at) -> int:
    run = EtlRun(
        job_id="test_ingest",
        window_start=start_at,
        window_end=end_at,
        status="running",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    return run.id


async def test_ingest_is_idempotent_and_advances_watermark(db_session) -> None:
    start_at = datetime(2026, 10, 26)
    end_at = start_at + timedelta(days=1)
    run_id = await create_run(db_session, start_at, end_at)
    service = IngestionService(
        db_session,
        Settings(_env_file=None),
        adapter_factory=FakeFactory(FakeAdapter([make_row("o1"), make_row("o2")])),
    )

    assert await service.run(make_job(), run_id, start_at, end_at) == 2
    assert await service.run(make_job(), run_id, start_at, end_at) == 2

    orders = (await db_session.execute(select(OdsOrder))).scalars().all()
    assert len(orders) == 2

    logs = (await db_session.execute(select(OdsFetchLog))).scalars().all()
    assert len(logs) == 2
    assert all(log.status == "success" for log in logs)

    watermark = await db_session.get(EtlWatermark, ("orders", "douyin"))
    assert watermark is not None
    assert watermark.last_success_at == end_at

    model_runs = (
        (
            await db_session.execute(
                select(EtlModelRun).where(EtlModelRun.run_id == run_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(model_runs) == 2
    assert all(item.layer == "ods" for item in model_runs)


async def test_backfill_does_not_lower_watermark(db_session) -> None:
    start_at = datetime(2026, 10, 26)
    end_at = start_at + timedelta(days=1)
    run_id = await create_run(db_session, start_at, end_at)
    service = IngestionService(
        db_session,
        Settings(_env_file=None),
        adapter_factory=FakeFactory(FakeAdapter([make_row("o1")])),
    )
    await service.run(make_job(), run_id, start_at, end_at)

    older_start = start_at - timedelta(days=2)
    await service.run(make_job(), run_id, older_start, start_at)
    watermark = await db_session.get(EtlWatermark, ("orders", "douyin"))
    assert watermark is not None
    assert watermark.last_success_at == end_at


async def test_failure_writes_failed_log_and_reraises(db_session) -> None:
    start_at = datetime(2026, 10, 26)
    end_at = start_at + timedelta(days=1)
    run_id = await create_run(db_session, start_at, end_at)
    service = IngestionService(
        db_session,
        Settings(_env_file=None),
        adapter_factory=FakeFactory(FakeAdapter([], fail=True)),
    )

    with pytest.raises(PermanentError, match="fetch failed"):
        await service.run(make_job(), run_id, start_at, end_at)

    logs = (await db_session.execute(select(OdsFetchLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].status == "failed"
    assert "fetch failed" in (logs[0].error or "")
