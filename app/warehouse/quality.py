from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EtlQualityResult


@dataclass(frozen=True)
class QualityCheck:
    model_name: str
    test_name: str
    sql: str
    expected_zero: bool = True


async def run_checks(
    session: AsyncSession,
    run_id: int,
    checks: list[QualityCheck],
) -> list[EtlQualityResult]:
    results: list[EtlQualityResult] = []
    for check in checks:
        value = (await session.execute(text(check.sql))).scalar_one()
        passed = (value == 0) if check.expected_zero else (value > 0)
        result = EtlQualityResult(
            run_id=run_id,
            model_name=check.model_name,
            test_name=check.test_name,
            status="passed" if passed else "failed",
            details=f"value={value}",
        )
        session.add(result)
        results.append(result)
    await session.commit()
    return results
