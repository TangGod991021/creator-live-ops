import asyncio

from app.scheduler.lanes import LaneManager


async def test_same_lane_serializes() -> None:
    manager = LaneManager({"l1": 1})
    active = 0
    peak = 0

    async def work() -> None:
        nonlocal active, peak
        async with manager.semaphore("l1"):
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(work() for _ in range(3)))
    assert peak == 1


async def test_different_lanes_parallel() -> None:
    manager = LaneManager({"l1": 1, "l2": 1})
    started = []

    async def work(lane: str) -> None:
        async with manager.semaphore(lane):
            started.append(lane)
            await asyncio.sleep(0.01)

    await asyncio.gather(work("l1"), work("l2"))
    assert set(started) == {"l1", "l2"}
