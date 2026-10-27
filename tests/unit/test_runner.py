from datetime import datetime
from pathlib import Path

import pytest

from app.warehouse.quality import QualityCheck, run_checks
from app.warehouse.renderer import TableRenderer
from app.warehouse.runner import PipelineRunner


class FakeResult:
    rowcount = 2

    def scalar_one(self) -> int:
        return 0


class FakeSession:
    def __init__(self, fail_on: str | None = None) -> None:
        self.executed: list[str] = []
        self.added: list = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_on = fail_on

    async def execute(self, statement):
        sql = str(statement)
        self.executed.append(sql)
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("boom")
        return FakeResult()

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def write_model(
    directory: Path,
    filename: str,
    layer: str,
    target: str,
    depends_on: str,
    sql: str,
) -> None:
    path = directory / filename
    path.write_text(
        f"-- @layer: {layer}\n"
        f"-- @target: {target}\n"
        f"-- @depends_on: {depends_on}\n"
        f"-- @window: day\n\n"
        f"{sql}\n",
        encoding="utf-8",
    )


async def test_runner_executes_in_dag_order(tmp_path: Path) -> None:
    write_model(
        tmp_path,
        "010_ods.sql",
        "ods",
        "ods_demo",
        "",
        "INSERT INTO {{ ref('ods_demo') }} VALUES (1);",
    )
    write_model(
        tmp_path,
        "100_dwd.sql",
        "dwd",
        "dwd_demo",
        "ods_demo",
        "INSERT INTO {{ ref('dwd_demo') }} SELECT * FROM {{ ref('ods_demo') }};",
    )
    session = FakeSession()
    runner = PipelineRunner(session, str(tmp_path), TableRenderer("single_db"))

    await runner.run(1, datetime(2026, 10, 25), datetime(2026, 10, 26))

    assert len(session.executed) == 2
    assert "INSERT INTO ods_demo" in session.executed[0]
    assert "INSERT INTO dwd_demo" in session.executed[1]
    assert [obj.status for obj in session.added] == ["success", "success"]
    assert session.commits == 2


async def test_runner_records_failure_and_raises(tmp_path: Path) -> None:
    write_model(tmp_path, "010_ods.sql", "ods", "ods_demo", "", "SELECT 'FAIL';")
    session = FakeSession(fail_on="FAIL")
    runner = PipelineRunner(session, str(tmp_path), TableRenderer("single_db"))

    with pytest.raises(RuntimeError, match="boom"):
        await runner.run(1, datetime(2026, 10, 25), datetime(2026, 10, 26))

    assert session.rollbacks == 1
    assert session.added[0].status == "failed"
    assert session.added[0].error == "boom"


async def test_quality_check_records_result() -> None:
    session = FakeSession()
    results = await run_checks(
        session,
        1,
        [QualityCheck("ads_demo", "gmv_not_null", "SELECT 0")],
    )
    assert results[0].status == "passed"
    assert session.commits == 1
