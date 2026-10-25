"""Shared fixtures: virtual time, fake collaborators and an event feeder."""

import asyncio
import heapq
import itertools
from datetime import UTC, datetime
import pytest

from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType
from opencloudtouch.presets.models import Preset
from opencloudtouch.streamrecovery.repository import StreamRecoveryRepository
from opencloudtouch.streamrecovery.service import StreamRecoveryService

DEVICE = "AABBCC112233"


async def settle(rounds: int = 25) -> None:
    """Let ready tasks run (real event loop, no virtual time involved)."""
    for _ in range(rounds):
        await asyncio.sleep(0)


async def finish(service, timeout: float = 2.0) -> None:
    """Wait (real time) until every running recovery sequence has ended.

    Sequences write to SQLite through a worker thread, which `settle` cannot wait for.
    """
    tasks = [s.task for s in list(service._sequences.values()) if s.task is not None]
    if tasks:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout)
    await settle()


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


class FakeDeviceService:
    def __init__(self, vtime: VirtualTime) -> None:
        self._vtime = vtime
        self.presses: list[tuple[str, str, str, float]] = []
        self.press_errors: list[BaseException | None] = []
        self.missing_devices: set[str] = set()

    async def press_key(self, device_id: str, key: str, state: str = "both") -> None:
        self.presses.append((device_id, key, state, self._vtime.t))
        if self.press_errors:
            error = self.press_errors.pop(0)
            if error is not None:
                raise error

    async def get_device_by_id(self, device_id: str):
        return None if device_id in self.missing_devices else object()


class FakePresetService:
    def __init__(self) -> None:
        self.presets: dict[str, list[Preset]] = {}

    async def get_all_presets(self, device_id: str) -> list[Preset]:
        return list(self.presets.get(device_id, []))


def make_preset(number: int, name: str, device_id: str = DEVICE) -> Preset:
    return Preset(
        device_id=device_id,
        preset_number=number,
        station_uuid=f"uuid-{number}",
        station_name=name,
        station_url=f"https://example.invalid/{number}",
    )


def now_playing_event(
    source: str,
    state: str,
    station: str | None = None,
    device_id: str = DEVICE,
    event_type: EventType = EventType.NOW_PLAYING,
) -> DeviceEvent:
    return DeviceEvent(
        device_id=device_id,
        event_type=event_type,
        now_playing=NowPlayingInfo(source=source, state=state, station_name=station),
    )


@pytest.fixture
def vtime() -> VirtualTime:
    return VirtualTime()


@pytest.fixture
def state_manager() -> DeviceStateManager:
    return DeviceStateManager()


@pytest.fixture
def devices(vtime) -> FakeDeviceService:
    return FakeDeviceService(vtime)


@pytest.fixture
def presets() -> FakePresetService:
    service = FakePresetService()
    service.presets[DEVICE] = [make_preset(1, "Other FM"), make_preset(2, "Radio X")]
    return service


@pytest.fixture
async def repository(tmp_path):
    repo = StreamRecoveryRepository(tmp_path / "oct.db")
    await repo.initialize()
    yield repo
    await repo.close()


@pytest.fixture
async def service(state_manager, devices, presets, repository, vtime):
    svc = StreamRecoveryService(
        state_manager=state_manager,
        device_service=devices,
        preset_service=presets,
        repository=repository,
        clock=vtime.clock,
        sleep=vtime.sleep,
        now=lambda: datetime(2026, 10, 26, 5, 52, 8, tzinfo=UTC),
    )
    await svc.start()
    yield svc
    await svc.stop()


@pytest.fixture
def feed(state_manager):
    """Publish an event to the service's queue (bypassing the SSE throttle)."""

    async def _feed(event: DeviceEvent) -> None:
        await state_manager.publish(event)
        await settle()

    return _feed


@pytest.fixture
def enabled(service):
    """Enable the watchdog with min 600 s and the given attempt cap (default 3)."""

    async def _enable(min_play_seconds: int = 600, max_attempts: int = 3):
        return await service.set_config(True, min_play_seconds, max_attempts)

    return _enable


async def events_of(repository, limit: int = 100):
    return await repository.list_events(limit=limit)
