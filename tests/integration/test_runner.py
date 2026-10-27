from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Base, EtlRun
from app.warehouse.renderer import TableRenderer
from app.warehouse.runner import PipelineRunner

pytestmark = pytest.mark.integration


async def test_runner_executes_demo_pipeline(db_engine) -> None:
    import app.db.demo_models  # noqa: F401

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(db_engine, expire_on_commit=False)
    start_at = datetime(2026, 10, 25)
    end_at = start_at + timedelta(days=1)

    async with Session() as session:
        run = EtlRun(
            job_id="demo_pipeline",
            window_start=start_at,
            window_end=end_at,
            status="running",
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

        runner = PipelineRunner(session, "models", TableRenderer("single_db"))
        await runner.run(run.id, start_at, end_at)

        rows = (
            await session.execute(
                text("SELECT talent_id, gmv FROM ads_demo_talent_daily ORDER BY talent_id")
            )
        ).all()
        assert len(rows) == 2
        assert rows[0].talent_id == "talent_a"
        assert float(rows[0].gmv) == 498.00
        assert float(rows[1].gmv) == 498.00

        model_runs = (
            await session.execute(
                text("SELECT model_name, status FROM etl_model_run WHERE run_id=:run_id"),
                {"run_id": run.id},
            )
        ).all()
        assert len(model_runs) == 4
        assert all(row.status == "success" for row in model_runs)
