import pytest

from app.scheduler.lock import JobLock

pytestmark = pytest.mark.integration


async def test_only_one_owner_can_acquire(db_session) -> None:
    first = JobLock(db_session, owner="a")
    second = JobLock(db_session, owner="b")
    assert await first.acquire("demo_pipeline") is True
    assert await second.acquire("demo_pipeline") is False
    await first.release("demo_pipeline")
    assert await second.acquire("demo_pipeline") is True
