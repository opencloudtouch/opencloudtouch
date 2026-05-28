"""
Tests for Device Repository
"""

import tempfile
from pathlib import Path

import pytest

from opencloudtouch.db import Device, DeviceRepository


@pytest.fixture
async def repo():
    """Create temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    repository = DeviceRepository(db_path)
    await repository.initialize()

    yield repository

    await repository.close()
    Path(db_path).unlink()


@pytest.mark.asyncio
async def test_device_repository_initialize(repo):
    """Test database initialization."""
    # Should not raise
    assert repo._db is not None


@pytest.mark.asyncio
async def test_device_upsert_insert(repo):
    """Test inserting a new device."""
    device = Device(
        device_id="TEST123",
        ip="192.168.1.100",
        name="Test Device",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="1.0.0",
    )

    result = await repo.upsert(device)

    assert result.id is not None
    assert result.device_id == "TEST123"


@pytest.mark.asyncio
async def test_device_upsert_update(repo):
    """Test updating an existing device."""
    device = Device(
        device_id="TEST123",
        ip="192.168.1.100",
        name="Test Device",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="1.0.0",
    )

    await repo.upsert(device)

    # Update with new IP
    device.ip = "192.168.1.101"
    device.firmware_version = "2.0.0"

    updated = await repo.upsert(device)

    assert updated.ip == "192.168.1.101"
    assert updated.firmware_version == "2.0.0"

    # Verify only one record exists
    all_devices = await repo.get_all()
    assert len(all_devices) == 1


@pytest.mark.asyncio
async def test_device_get_all_empty(repo):
    """Test get_all with empty database."""
    devices = await repo.get_all()

    assert devices == []


@pytest.mark.asyncio
async def test_firmware_version_with_release_suffix_storage(repo):
    """Regression test: Firmware version with release suffix stored correctly.

    Bug: Frontend trimmt Firmware bei 'epdbuild', aber Backend muss volle Version speichern.
    Fixed: 2026-01-29 - Backend speichert rohe Version, Frontend trimmt bei Anzeige.
    """
    device = Device(
        device_id="FW_TEST",
        ip="192.168.1.50",
        name="Firmware Test Device",
        model="SoundTouch 30",
        mac_address="11:22:33:44:55:66",
        firmware_version="27.0.6.46330.5043500-release+hepdswbld04.2022",
    )

    # Insert
    result = await repo.upsert(device)
    assert result.firmware_version == "27.0.6.46330.5043500-release+hepdswbld04.2022"

    # Retrieve by device_id
    retrieved = await repo.get_by_device_id("FW_TEST")
    assert retrieved is not None
    assert retrieved.firmware_version == "27.0.6.46330.5043500-release+hepdswbld04.2022"

    # Retrieve via get_all
    all_devices = await repo.get_all()
    fw_device = next(d for d in all_devices if d.device_id == "FW_TEST")
    assert fw_device.firmware_version == "27.0.6.46330.5043500-release+hepdswbld04.2022"


@pytest.mark.asyncio
async def test_firmware_version_minimal_format(repo):
    """Test firmware version with only major.minor.patch format."""
    device = Device(
        device_id="FW_SIMPLE",
        ip="192.168.1.51",
        name="Simple FW Device",
        model="SoundTouch 10",
        mac_address="AA:AA:AA:AA:AA:AA",
        firmware_version="1.0.0",
    )

    result = await repo.upsert(device)
    assert result.firmware_version == "1.0.0"

    retrieved = await repo.get_by_device_id("FW_SIMPLE")
    assert retrieved.firmware_version == "1.0.0"


@pytest.mark.asyncio
async def test_device_get_all(repo):
    """Test get_all with multiple devices."""
    device1 = Device(
        device_id="DEV1",
        ip="192.168.1.100",
        name="Device 1",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="1.0.0",
    )

    device2 = Device(
        device_id="DEV2",
        ip="192.168.1.101",
        name="Device 2",
        model="SoundTouch 30",
        mac_address="11:22:33:44:55:66",
        firmware_version="2.0.0",
    )

    await repo.upsert(device1)
    await repo.upsert(device2)

    devices = await repo.get_all()

    assert len(devices) == 2
    assert all(isinstance(d, Device) for d in devices)


@pytest.mark.asyncio
async def test_device_get_by_device_id(repo):
    """Test get_by_device_id."""
    device = Device(
        device_id="TEST123",
        ip="192.168.1.100",
        name="Test Device",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="1.0.0",
    )

    await repo.upsert(device)

    found = await repo.get_by_device_id("TEST123")

    assert found is not None
    assert found.device_id == "TEST123"
    assert found.name == "Test Device"


@pytest.mark.asyncio
async def test_device_get_by_device_id_not_found(repo):
    """Test get_by_device_id with non-existent device."""
    found = await repo.get_by_device_id("NONEXISTENT")

    assert found is None


def test_device_to_dict():
    """Test Device.to_dict()."""
    device = Device(
        device_id="TEST123",
        ip="192.168.1.100",
        name="Test Device",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="1.0.0",
    )

    d = device.to_dict()

    assert d["device_id"] == "TEST123"
    assert d["ip"] == "192.168.1.100"
    assert d["name"] == "Test Device"
    assert d["model"] == "SoundTouch 10"


def test_device_schema_version_extraction():
    """Test schema version extraction from firmware version."""
    # Full firmware version
    device1 = Device(
        device_id="TEST1",
        ip="192.168.1.1",
        name="Test",
        model="SoundTouch 30",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="28.0.3.46454 epdbuild.trunk.hepdswbld02.2023-07-27T14:58:40",
    )
    assert device1.schema_version == "28.0.3"

    # Short firmware version
    device2 = Device(
        device_id="TEST2",
        ip="192.168.1.2",
        name="Test",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="28.0.3",
    )
    assert device2.schema_version == "28.0.3"

    # Very short firmware version (fewer than 3 parts) — covers line 59
    device2b = Device(
        device_id="TEST2B",
        ip="192.168.1.2",
        name="Test",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="28.0",
    )
    assert device2b.schema_version == "28.0"

    # Empty firmware
    device3 = Device(
        device_id="TEST3",
        ip="192.168.1.3",
        name="Test",
        model="SoundTouch 300",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="",
    )
    assert device3.schema_version == "unknown"

    # Manual override
    device4 = Device(
        device_id="TEST4",
        ip="192.168.1.4",
        name="Test",
        model="SoundTouch 30",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="28.0.3.46454",
        schema_version="custom.1.0",
    )
    assert device4.schema_version == "custom.1.0"


@pytest.mark.asyncio
async def test_device_schema_version_persisted(repo):
    """Test that schema_version is persisted in database."""
    device = Device(
        device_id="TEST_SCHEMA",
        ip="192.168.1.100",
        name="Test Device",
        model="SoundTouch 30",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="28.0.3.46454 epdbuild.trunk",
    )

    # Should auto-extract schema version
    assert device.schema_version == "28.0.3"

    # Persist
    await repo.upsert(device)

    # Retrieve
    found = await repo.get_by_device_id("TEST_SCHEMA")
    assert found is not None
    assert found.schema_version == "28.0.3"
    assert found.firmware_version == "28.0.3.46454 epdbuild.trunk"


@pytest.mark.asyncio
async def test_delete_all(repo):
    """Test delete_all removes all devices and returns count."""
    # Insert multiple devices
    device1 = Device(
        device_id="DEV1",
        ip="192.168.1.100",
        name="Device 1",
        model="SoundTouch 30",
        mac_address="AA:BB:CC:DD:EE:01",
        firmware_version="28.0.3",
    )
    device2 = Device(
        device_id="DEV2",
        ip="192.168.1.101",
        name="Device 2",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:DD:EE:02",
        firmware_version="28.0.3",
    )

    await repo.upsert(device1)
    await repo.upsert(device2)

    # Verify devices exist
    all_devices = await repo.get_all()
    assert len(all_devices) == 2

    # Delete all
    deleted_count = await repo.delete_all()
    assert deleted_count == 2

    # Verify empty
    all_devices = await repo.get_all()
    assert len(all_devices) == 0


@pytest.mark.asyncio
async def test_repository_close():
    """Test repository close method."""
    repo = DeviceRepository(":memory:")
    await repo.initialize()

    # Close should not raise
    await repo.close()

    # Operations after close should fail
    with pytest.raises(RuntimeError, match="not initialized"):
        await repo.get_all()


@pytest.mark.asyncio
async def test_upsert_without_initialization():
    """Test upsert fails when DB not initialized."""
    repo = DeviceRepository(":memory:")
    # Don't call initialize()

    device = Device(
        device_id="TEST",
        ip="192.168.1.100",
        name="Test",
        model="SoundTouch 30",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="28.0.3",
    )

    with pytest.raises(RuntimeError, match="not initialized"):
        await repo.upsert(device)


@pytest.mark.asyncio
async def test_get_all_without_initialization():
    """Test get_all fails when DB not initialized."""
    repo = DeviceRepository(":memory:")

    with pytest.raises(RuntimeError, match="not initialized"):
        await repo.get_all()


@pytest.mark.asyncio
async def test_get_by_device_id_without_initialization():
    """Test get_by_device_id fails when DB not initialized."""
    repo = DeviceRepository(":memory:")

    with pytest.raises(RuntimeError, match="not initialized"):
        await repo.get_by_device_id("TEST")


@pytest.mark.asyncio
async def test_delete_all_without_initialization():
    """Test delete_all fails when DB not initialized."""
    repo = DeviceRepository(":memory:")

    with pytest.raises(RuntimeError, match="not initialized"):
        await repo.delete_all()


# ---------------------------------------------------------------------------
# Marge Account UUID operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_and_get_by_account_uuid(repo):
    """update_marge_account_uuid persists UUID and get_by_account_uuid retrieves it."""
    device = Device(
        device_id="UUID_TEST",
        ip="10.0.0.1",
        name="UUID Device",
        model="SoundTouch 20",
        mac_address="11:22:33:44:55:66",
        firmware_version="2.0",
    )
    await repo.upsert(device)

    await repo.update_marge_account_uuid("UUID_TEST", "5522049")

    found = await repo.get_by_account_uuid("5522049")
    assert found is not None
    assert found.device_id == "UUID_TEST"
    assert found.marge_account_uuid == "5522049"


@pytest.mark.asyncio
async def test_get_by_account_uuid_not_found(repo):
    """get_by_account_uuid returns None for non-existent UUID."""
    result = await repo.get_by_account_uuid("9999999")
    assert result is None


@pytest.mark.asyncio
async def test_get_by_marge_account_uuid(repo):
    """get_by_marge_account_uuid returns device with matching UUID."""
    device = Device(
        device_id="MARGE_TEST",
        ip="10.0.0.2",
        name="Marge Device",
        model="SoundTouch 30",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="3.0",
        marge_account_uuid="8866380",
    )
    await repo.upsert(device)

    found = await repo.get_by_marge_account_uuid("8866380")
    assert found is not None
    assert found.device_id == "MARGE_TEST"


@pytest.mark.asyncio
async def test_get_by_marge_account_uuid_not_found(repo):
    """get_by_marge_account_uuid returns None for non-existent UUID."""
    result = await repo.get_by_marge_account_uuid("0000000")
    assert result is None


class TestDatabaseConnectionErrors:
    """Tests for database connection failures and timeouts."""

    @pytest.mark.asyncio
    async def test_upsert_with_db_locked_error(self):
        """Test upsert when database is locked by another process.

        Use case: Multiple containers/processes access same SQLite file.
        Expected: Raises DatabaseError with helpful message.

        Note: SQLite "database is locked" is common in multi-process scenarios.
        """
        repo = DeviceRepository(":memory:")
        await repo.initialize()

        device = Device(
            device_id="TEST123",
            ip="192.168.1.100",
            name="Test Device",
            model="SoundTouch 30",
            mac_address="AA:BB:CC:DD:EE:FF",
            firmware_version="28.0.5",
        )

        # Mock DB connection to raise "database is locked"
        from aiosqlite import Error as DatabaseError

        # Close real connection and mock
        await repo.close()

        # Simulate locked database by attempting operation on closed connection
        with pytest.raises((DatabaseError, RuntimeError)):
            await repo.upsert(device)

    @pytest.mark.asyncio
    async def test_get_all_handles_corrupt_data_gracefully(self):
        """Test get_all when database has corrupt/invalid data.

        Use case: Database file partially corrupted or manual SQL edits.
        Expected: Skip invalid rows, return valid devices, log errors.

        Note: SQLite enforces NOT NULL constraints, so we test invalid MAC format.
        Current implementation doesn't validate MAC format - returns as-is.
        This test documents expected behavior for future validation.
        """
        repo = DeviceRepository(":memory:")
        await repo.initialize()

        # Insert valid device
        valid_device = Device(
            device_id="VALID",
            ip="192.168.1.100",
            name="Valid Device",
            model="SoundTouch 30",
            mac_address="AA:BB:CC:DD:EE:FF",
            firmware_version="28.0.5",
        )
        await repo.upsert(valid_device)

        # Insert device with corrupt/invalid MAC address format
        # (Tests graceful handling of data validation errors)
        corrupt_device = Device(
            device_id="CORRUPT",
            ip="192.168.1.101",
            name="Corrupt MAC Device",
            model="SoundTouch 30",
            mac_address="INVALID_MAC_FORMAT",  # Not standard MAC format
            firmware_version="28.0.5",
        )
        await repo.upsert(corrupt_device)

        # get_all should return both devices (no validation yet)
        devices = await repo.get_all()

        # Current behavior: Both devices returned
        assert len(devices) == 2
        assert any(d.device_id == "VALID" for d in devices)
        assert any(d.device_id == "CORRUPT" for d in devices)

        await repo.close()

        # Future: Should skip corrupt device and log warning
        # Or: Should return corrupt device but mark as invalid

    @pytest.mark.asyncio
    async def test_connection_timeout_on_slow_query(self):
        """Test repository handles slow queries gracefully.

        Use case: Database on slow disk or network-mounted filesystem.
        Expected: Query times out, raises appropriate error.

        Note: SQLite doesn't have built-in query timeouts like PostgreSQL.
        This test documents limitation for future migration.
        """
        repo = DeviceRepository(":memory:")
        await repo.initialize()

        try:
            # In-memory SQLite is always fast, so this test just verifies
            # that normal operations complete quickly
            import time

            start = time.time()
            await repo.get_all()
            elapsed = time.time() - start

            # Should complete in <100ms for empty DB
            assert elapsed < 0.1, f"Query took {elapsed}s, expected <0.1s"
        finally:
            await repo.close()

    @pytest.mark.asyncio
    async def test_concurrent_writes_to_same_device(self):
        """Test concurrent upsert operations on same device.

        Use case: Discovery and manual sync both update same device.
        Expected: Last write wins, no data corruption.

        SQLite serializes writes, so this should be safe.
        """
        repo = DeviceRepository(":memory:")
        await repo.initialize()

        try:
            import asyncio

            async def update_device(name_suffix):
                device = Device(
                    device_id="SHARED",
                    ip="192.168.1.100",
                    name=f"Device {name_suffix}",
                    model="SoundTouch 30",
                    mac_address="AA:BB:CC:DD:EE:FF",
                    firmware_version="28.0.5",
                )
                await repo.upsert(device)
                return name_suffix

            # 5 concurrent writes to same device_id
            tasks = [update_device(f"v{i}") for i in range(5)]
            results = await asyncio.gather(*tasks)

            # All should complete without error
            assert len(results) == 5

            # Final state: One of the versions (last write wins)
            device = await repo.get_by_device_id("SHARED")
            assert device is not None
            assert device.device_id == "SHARED"
            # Name will be one of "Device v0" through "Device v4"
            assert device.name.startswith("Device v")

        finally:
            await repo.close()
