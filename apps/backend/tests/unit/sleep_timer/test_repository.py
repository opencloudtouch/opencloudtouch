"""SleepTimerRepository: one row per device, UTC ISO times, survives reopening."""

import aiosqlite
import pytest

from opencloudtouch.sleep_timer.models import SleepTimer
from opencloudtouch.sleep_timer.repository import SleepTimerRepository, from_iso, to_iso

DEVICE = "AABBCC112233"


@pytest.fixture
async def repo(tmp_path):
    repository = SleepTimerRepository(tmp_path / "oct.db")
    await repository.initialize()
    yield repository
    await repository.close()


def _timer(device_id=DEVICE, ends_at=1_800_000_000.0, **overrides) -> SleepTimer:
    values = {
        "device_id": device_id,
        "ends_at": ends_at,
        "duration_minutes": 30,
        "fade_seconds": 30,
        "end_action": "stop",
        "original_volume": None,
        "created_at": ends_at - 1800,
    }
    values.update(overrides)
    return SleepTimer(**values)


def test_iso_round_trip_is_utc_with_z():
    assert to_iso(0) == "1970-01-01T00:00:00Z"
    assert from_iso(to_iso(1_800_000_000)) == 1_800_000_000


@pytest.mark.asyncio
async def test_unknown_device_has_no_timer(repo):
    assert await repo.get(DEVICE) is None


@pytest.mark.asyncio
async def test_round_trip(repo):
    await repo.upsert(_timer(original_volume=40, end_action="standby"))
    assert await repo.get(DEVICE) == _timer(original_volume=40, end_action="standby")


@pytest.mark.asyncio
async def test_upsert_replaces_the_row_of_the_device(repo):
    await repo.upsert(_timer())
    await repo.upsert(_timer(ends_at=1_800_003_600.0, duration_minutes=60))
    timers = await repo.list_all()
    assert len(timers) == 1
    assert timers[0].duration_minutes == 60


@pytest.mark.asyncio
async def test_set_original_volume_and_clear_it(repo):
    await repo.upsert(_timer())
    await repo.set_original_volume(DEVICE, 33)
    assert (await repo.get(DEVICE)).original_volume == 33
    await repo.set_original_volume(DEVICE, None)
    assert (await repo.get(DEVICE)).original_volume is None


@pytest.mark.asyncio
async def test_set_last_set_volume(repo):
    await repo.upsert(_timer(original_volume=40))
    await repo.set_last_set_volume(DEVICE, 12)
    assert (await repo.get(DEVICE)).last_set_volume == 12
    await repo.upsert(_timer(original_volume=40, last_set_volume=7))
    assert (await repo.get(DEVICE)).last_set_volume == 7


@pytest.mark.asyncio
async def test_delete_is_idempotent(repo):
    await repo.upsert(_timer())
    await repo.delete(DEVICE)
    await repo.delete(DEVICE)
    assert await repo.get(DEVICE) is None


@pytest.mark.asyncio
async def test_list_is_ordered_by_end_time(repo):
    await repo.upsert(_timer("B", ends_at=1_800_000_900.0))
    await repo.upsert(_timer("A", ends_at=1_800_000_100.0))
    assert [t.device_id for t in await repo.list_all()] == ["A", "B"]


@pytest.mark.asyncio
async def test_unknown_end_action_is_rejected_by_the_schema(repo):
    bad = _timer(end_action="explode")
    with pytest.raises(aiosqlite.IntegrityError):
        await repo.upsert(bad)


@pytest.mark.asyncio
async def test_survives_reopening_the_database(tmp_path):
    first = SleepTimerRepository(tmp_path / "oct.db")
    await first.initialize()
    await first.upsert(_timer(original_volume=12))
    await first.close()

    second = SleepTimerRepository(tmp_path / "oct.db")
    await second.initialize()
    assert (await second.get(DEVICE)).original_volume == 12
    await second.close()
