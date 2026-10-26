"""Deterministic time for service tests: injectable clock and sleep."""

import asyncio
import heapq
import itertools


async def settle(rounds: int = 25) -> None:
    """Let ready tasks run (real event loop, no virtual time involved)."""
    for _ in range(rounds):
        await asyncio.sleep(0)


class VirtualTime:
    """Injectable clock + sleep: sleeping blocks until the test advances time."""

    def __init__(self) -> None:
        self.t = 10_000.0
        self._waiters: list[tuple[float, int, asyncio.Future]] = []
        self._counter = itertools.count()

    def clock(self) -> float:
        return self.t

    async def sleep(self, seconds: float) -> None:
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        heapq.heappush(self._waiters, (self.t + seconds, next(self._counter), future))
        await future

    def jump(self, seconds: float) -> None:
        """Move the clock without waking sleepers (e.g. 'the station played for 6 h')."""
        self.t += seconds

    async def advance(self, seconds: float) -> None:
        """Move the clock and wake every sleeper that becomes due, in order."""
        target = self.t + seconds
        await settle()
        while self._waiters and self._waiters[0][0] <= target:
            when, _, future = heapq.heappop(self._waiters)
            if future.cancelled():
                continue
            self.t = max(self.t, when)
            future.set_result(None)
            await settle()
        self.t = target
        await settle()
