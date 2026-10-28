"""StreamRecoveryRepository: single-row config and a capped event log."""

import aiosqlite
import pytest

from opencloudtouch.streamrecovery.models import (
    StreamRecoveryConfig,
    StreamRecoveryEvent,
)
from opencloudtouch.streamrecovery.repository import StreamRecoveryRepository


@pytest.fixture
async def repo(tmp_path):
    repository = StreamRecoveryRepository(tmp_path / "oct.db")
    await repository.initialize()
    yield repository
    await repository.close()


def _event(n: int = 1, outcome: str = "resumed", **overrides) -> StreamRecoveryEvent:
    values = {
        "occurred_at": f"2026-10-26T05:{n % 60:02d}:00Z",
        "device_id": "AABBCC112233",
        "preset_number": 2,
        "station_name": f"Radio {n}",
        "play_seconds": 21600,
        "outcome": outcome,
        "attempts": 1,
        "error_code": None,
    }
    values.update(overrides)
    return StreamRecoveryEvent(**values)


class TestConfig:
    @pytest.mark.asyncio
    async def test_fresh_database_returns_defaults(self, repo):
        assert await repo.get_config() == StreamRecoveryConfig(
            enabled=False,
            min_play_seconds=600,
            max_attempts_per_hour=3,
            updated_at=None,
        )

    @pytest.mark.asyncio
    async def test_set_config_is_returned_with_utc_timestamp(self, repo):
        stored = await repo.set_config(True, 300, 2)

        assert (
            stored.enabled,
            stored.min_play_seconds,
            stored.max_attempts_per_hour,
        ) == (
            True,
            300,
            2,
        )
        assert stored.updated_at is not None
        assert stored.updated_at.endswith("Z")
        assert await repo.get_config() == stored

    @pytest.mark.asyncio
    async def test_second_write_replaces_the_single_row(self, repo):
        await repo.set_config(True, 300, 2)
        await repo.set_config(False, 900, 5)

        async with aiosqlite.connect(repo.db_path) as db:
            rows = await (
                await db.execute("SELECT id FROM stream_recovery_config")
            ).fetchall()
        assert rows == [(1,)]
        assert (await repo.get_config()).max_attempts_per_hour == 5

    @pytest.mark.asyncio
    async def test_config_survives_reopening_the_file(self, tmp_path):
        first = StreamRecoveryRepository(tmp_path / "oct.db")
        await first.initialize()
        await first.set_config(True, 300, 2)
        await first.close()

        second = StreamRecoveryRepository(tmp_path / "oct.db")
        await second.initialize()
        try:
            config = await second.get_config()
        finally:
            await second.close()

        assert (
            config.enabled,
            config.min_play_seconds,
            config.max_attempts_per_hour,
        ) == (
            True,
            300,
            2,
        )
        assert config.updated_at is not None


class TestEvents:
    @pytest.mark.asyncio
    async def test_newest_first_and_limit(self, repo):
        for n in range(1, 6):
            await repo.add_event(_event(n))

        events = await repo.list_events(limit=3)

        assert [e.station_name for e in events] == ["Radio 5", "Radio 4", "Radio 3"]
        assert all(e.id is not None for e in events)

    @pytest.mark.asyncio
    async def test_all_fields_round_trip(self, repo):
        await repo.add_event(
            _event(
                1,
                outcome="gave_up",
                attempts=2,
                error_code="device_unreachable",
                preset_number=None,
                station_name=None,
                play_seconds=None,
            )
        )

        (event,) = await repo.list_events(limit=20)

        assert event.outcome == "gave_up"
        assert event.attempts == 2
        assert event.error_code == "device_unreachable"
        assert event.preset_number is None
        assert event.station_name is None
        assert event.play_seconds is None

    @pytest.mark.asyncio
    async def test_only_the_newest_100_rows_are_kept(self, repo):
        for n in range(101):
            await repo.add_event(_event(n))

        events = await repo.list_events(limit=100)

        assert len(events) == 100
        assert events[0].station_name == "Radio 100"
        assert events[-1].station_name == "Radio 1"  # Radio 0 was trimmed
        async with aiosqlite.connect(repo.db_path) as db:
            (count,) = await (
                await db.execute("SELECT COUNT(*) FROM stream_recovery_events")
            ).fetchone()
        assert count == 100

    @pytest.mark.asyncio
    async def test_unknown_outcome_is_rejected_by_the_schema(self, repo):
        bad = _event(1, outcome="exploded")
        with pytest.raises(aiosqlite.IntegrityError):
            await repo.add_event(bad)
        assert await repo.list_events(limit=20) == []
