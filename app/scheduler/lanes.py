import asyncio
from dataclasses import dataclass, field


@dataclass
class LaneManager:
    limits: dict[str, int]
    _semaphores: dict[str, asyncio.Semaphore] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._semaphores = {
            lane: asyncio.Semaphore(max(1, limit)) for lane, limit in self.limits.items()
        }

    def semaphore(self, lane: str) -> asyncio.Semaphore:
        if lane not in self._semaphores:
            self._semaphores[lane] = asyncio.Semaphore(1)
        return self._semaphores[lane]
