"""
Regression test for device removal cascade failure.

BUGFIX: Removing a device from the network causes ALL other devices to fail.

Date: 2026-04-06
Symptom: After removing one device from the network, navigating to the app
         on mobile shows "blurred" skeleton tiles instead of presets for ALL
         devices. Adding new devices also fails. Database wipe required to
         recover.

Root Cause: Multiple aiosqlite connections to the same database file without
            WAL mode and without busy_timeout. When concurrent write
            operations happen (e.g. health-check upsert + preset sync),
            SQLITE_BUSY errors occur. Without rollback-on-error, failed
            transactions leave dangling locks that block ALL subsequent
            database operations across ALL repositories.

Fix: Enable WAL journal mode and set busy_timeout in BaseRepository to
     handle concurrent access from multiple connections gracefully.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from opencloudtouch.db import Device, DeviceRepository
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository


@pytest.fixture
async def shared_db_path():
    """Provide a single DB file path shared by multiple repos."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "shared.db"


@pytest.fixture
async def device_repo(shared_db_path):
    repo = DeviceRepository(str(shared_db_path))
    await repo.initialize()
    yield repo
    await repo.close()


@pytest.fixture
async def preset_repo(shared_db_path):
    repo = PresetRepository(str(shared_db_path))
    await repo.initialize()
    yield repo
    await repo.close()


def _make_device(device_id: str, ip: str, name: str) -> Device:
    return Device(
        device_id=device_id,
        ip=ip,
        name=name,
        model="SoundTouch 10",
        mac_address=f"AA:BB:CC:DD:EE:{device_id[-2:]}",
        firmware_version="28.0.3.46454",
    )


def _make_preset(device_id: str, number: int, station_name: str) -> Preset:
    return Preset(
        device_id=device_id,
        preset_number=number,
        station_uuid=f"uuid-{station_name.lower().replace(' ', '-')}",
        station_name=station_name,
        station_url=f"http://stream.example.com/{station_name.lower()}.mp3",
    )


class TestDeviceRemovalCascadeFailure:
    """Regression: one offline device must NOT break preset loading for others."""

    @pytest.mark.asyncio
    async def test_concurrent_repo_writes_no_sqlite_busy(
        self, device_repo, preset_repo
    ):
        """Concurrent writes from two connections must not cause SQLITE_BUSY.

        Simulates: health-check upserts device while preset sync writes presets.
        Before fix (no WAL, no busy_timeout): SQLITE_BUSY → cascade failure.
        After fix: both operations succeed.
        """
        device = _make_device("DEV001", "192.168.1.10", "Living Room")
        await device_repo.upsert(device)

        # Run concurrent writes from two different connections
        errors = []

        async def health_check_writes():
            """Simulate health-check updating last_seen for many devices."""
            for i in range(20):
                try:
                    d = _make_device(f"HC{i:03d}", f"10.0.0.{i}", f"HC Device {i}")
                    await device_repo.upsert(d)
                except Exception as e:
                    errors.append(("health_check", i, e))

        async def preset_writes():
            """Simulate preset sync writing presets."""
            for i in range(20):
                try:
                    p = _make_preset("DEV001", (i % 6) + 1, f"Station {i}")
                    await preset_repo.set_preset(p)
                except Exception as e:
                    errors.append(("preset_sync", i, e))

        # Run both concurrently — this triggers the SQLITE_BUSY scenario
        await asyncio.gather(health_check_writes(), preset_writes())

        assert (
            errors == []
        ), f"Concurrent writes caused {len(errors)} errors: " + "; ".join(
            f"{src}[{idx}]: {err}" for src, idx, err in errors[:5]
        )

    @pytest.mark.asyncio
    async def test_preset_read_during_device_writes(self, device_repo, preset_repo):
        """Reading presets must work while device_repo is writing.

        This is the exact user scenario: loading presets page while
        background health-check updates device last_seen timestamps.
        """
        # Setup: device with presets
        device = _make_device("DEV_A", "192.168.1.10", "Kitchen Speaker")
        await device_repo.upsert(device)
        for i in range(1, 4):
            await preset_repo.set_preset(_make_preset("DEV_A", i, f"Radio {i}"))

        preset_read_results = []
        errors = []

        async def continuous_device_upserts():
            """Simulate health-check doing rapid upserts."""
            for i in range(30):
                try:
                    d = _make_device(f"BG{i:03d}", f"10.0.0.{i}", f"BG {i}")
                    await device_repo.upsert(d)
                except Exception as e:
                    errors.append(("upsert", i, e))

        async def read_presets_repeatedly():
            """Simulate frontend loading presets for DEV_A."""
            for _ in range(30):
                try:
                    presets = await preset_repo.get_all_presets("DEV_A")
                    preset_read_results.append(len(presets))
                except Exception as e:
                    errors.append(("read_presets", _, e))

        await asyncio.gather(continuous_device_upserts(), read_presets_repeatedly())

        assert (
            errors == []
        ), f"Concurrent read+write caused {len(errors)} errors: " + "; ".join(
            f"{src}[{idx}]: {err}" for src, idx, err in errors[:5]
        )
        # All reads should return 3 presets consistently
        assert all(
            count == 3 for count in preset_read_results
        ), f"Inconsistent preset reads: {set(preset_read_results)}"

    @pytest.mark.asyncio
    async def test_failed_write_does_not_poison_connection(
        self, device_repo, preset_repo
    ):
        """A failed write on one connection must not block the other.

        After a SQLITE_BUSY error (if it ever happens), subsequent
        operations on both connections must still work.
        """
        # Pre-populate
        d1 = _make_device("GOOD_DEV", "192.168.1.50", "Good Device")
        await device_repo.upsert(d1)
        await preset_repo.set_preset(_make_preset("GOOD_DEV", 1, "My Radio"))

        # Force heavy concurrent writes to increase chance of contention
        async def hammer_devices():
            for i in range(50):
                try:
                    d = _make_device(f"H{i:03d}", f"10.0.0.{i}", f"H{i}")
                    await device_repo.upsert(d)
                except Exception:
                    pass  # Some might fail — that's fine

        async def hammer_presets():
            for i in range(50):
                try:
                    p = _make_preset("GOOD_DEV", (i % 6) + 1, f"S{i}")
                    await preset_repo.set_preset(p)
                except Exception:
                    pass

        await asyncio.gather(hammer_devices(), hammer_presets())

        # CRITICAL: After the storm, BOTH connections MUST still work
        # This is what failed before the fix — the connection was "poisoned"
        devices = await device_repo.get_all()
        assert len(devices) > 0, "device_repo must be usable after concurrent writes"

        presets = await preset_repo.get_all_presets("GOOD_DEV")
        assert len(presets) > 0, "preset_repo must be usable after concurrent writes"

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, device_repo):
        """WAL journal mode must be enabled for concurrent access support."""
        cursor = await device_repo._db.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row[0].lower() == "wal", (
            f"Expected WAL journal mode, got '{row[0]}'. "
            "Without WAL, concurrent connections will cause SQLITE_BUSY errors."
        )

    @pytest.mark.asyncio
    async def test_busy_timeout_set(self, device_repo):
        """busy_timeout must be set to avoid immediate SQLITE_BUSY failures."""
        cursor = await device_repo._db.execute("PRAGMA busy_timeout")
        row = await cursor.fetchone()
        assert row[0] >= 3000, (
            f"Expected busy_timeout >= 3000ms, got {row[0]}ms. "
            "Without busy_timeout, concurrent access fails immediately."
        )
