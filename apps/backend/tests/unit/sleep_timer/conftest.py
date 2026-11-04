"""Fixtures: virtual clock, scripted devices and a service on an in-memory store."""

import asyncio

import pytest

from opencloudtouch.devices.volume_fader import step_target
from opencloudtouch.sleep_timer.service import SleepTimerService
from tests.unit.helpers.fake_playback import FakePlaybackDevices
from tests.unit.helpers.memory_repos import InMemorySleepTimerRepository
from tests.unit.helpers.virtual_time import VirtualTime, settle

DEVICE = "AABBCC112233"


@pytest.fixture
def vtime() -> VirtualTime:
    return VirtualTime()


@pytest.fixture
def devices() -> FakePlaybackDevices:
    return FakePlaybackDevices(DEVICE)


@pytest.fixture
def repository() -> InMemorySleepTimerRepository:
    return InMemorySleepTimerRepository()


@pytest.fixture
def make_service(devices, repository, vtime):
    def factory() -> SleepTimerService:
        service = SleepTimerService(
            device_service=devices,
            repository=repository,
            clock=vtime.clock,
            sleep=vtime.sleep,
        )
        return service

    return factory


@pytest.fixture
def service(make_service) -> SleepTimerService:
    return make_service()


async def drain(service: SleepTimerService, timeout: float = 2.0) -> None:
    """Wait (real time) until every timer task has ended."""
    tasks = list(service._tasks.values())
    if tasks:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout)
    await settle()


def fade_values(from_v: int, to_v: int, seconds: int) -> list[int]:
    """The distinct, consecutive volumes the fader writes (formula, not literals)."""
    import math

    steps = min(150, max(1, math.ceil(seconds / 2)))
    values: list[int] = []
    previous = from_v
    for i in range(1, steps + 1):
        value = step_target(from_v, to_v, i, steps)
        if value != previous:
            values.append(value)
            previous = value
    return values
