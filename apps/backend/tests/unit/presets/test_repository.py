"""Tests for preset repository."""

import tempfile
from pathlib import Path
import pytest

from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository


@pytest.fixture
async def preset_repo():
    """Create a temporary preset repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_presets.db"
        repo = PresetRepository(str(db_path))
        await repo.initialize()
        yield repo
        await repo.close()


@pytest.fixture
def sample_preset_data():
    """Sample preset data for testing."""
    return {
        "device_id": "device123",
        "preset_number": 1,
        "station_uuid": "station-uuid-abc",
        "station_name": "Test Radio",
        "station_url": "http://test.radio/stream.mp3",
        "station_homepage": "https://test.radio",
        "station_favicon": "https://test.radio/favicon.ico",
    }


class TestPresetRepository:
    """Tests for PresetRepository."""

    @pytest.mark.asyncio
    async def test_initialize_creates_table(self, preset_repo):
        """Test that initialize creates the presets table."""
        # Table should exist after initialization
        cursor = await preset_repo._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='presets'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "presets"

    @pytest.mark.asyncio
    async def test_set_preset_insert(self, preset_repo, sample_preset_data):
        """Test setting a new preset."""
        preset = Preset(**sample_preset_data)

        result = await preset_repo.set_preset(preset)

        assert result.id is not None
        assert result.device_id == "device123"
        assert result.preset_number == 1
        assert result.station_uuid == "station-uuid-abc"
        assert result.station_name == "Test Radio"

    @pytest.mark.asyncio
    async def test_set_preset_update(self, preset_repo, sample_preset_data):
        """Test updating an existing preset."""
        # Insert initial preset
        preset1 = Preset(**sample_preset_data)
        await preset_repo.set_preset(preset1)

        # Update same device/preset_number with different station
        preset2 = Preset(
            device_id="device123",
            preset_number=1,
            station_uuid="new-station-uuid",
            station_name="New Radio",
            station_url="http://new.radio/stream.mp3",
        )

        result = await preset_repo.set_preset(preset2)

        assert result.station_uuid == "new-station-uuid"
        assert result.station_name == "New Radio"

        # Verify only one preset exists
        all_presets = await preset_repo.get_all_presets("device123")
        assert len(all_presets) == 1
        assert all_presets[0].station_name == "New Radio"

    @pytest.mark.asyncio
    async def test_get_preset_existing(self, preset_repo, sample_preset_data):
        """Test getting an existing preset."""
        preset = Preset(**sample_preset_data)
        await preset_repo.set_preset(preset)

        result = await preset_repo.get_preset("device123", 1)

        assert result is not None
        assert result.device_id == "device123"
        assert result.preset_number == 1
        assert result.station_name == "Test Radio"

    @pytest.mark.asyncio
    async def test_get_preset_nonexistent(self, preset_repo):
        """Test getting a nonexistent preset returns None."""
        result = await preset_repo.get_preset("nonexistent", 1)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_presets_empty(self, preset_repo):
        """Test getting all presets for device with none set."""
        result = await preset_repo.get_all_presets("device123")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_presets_multiple(self, preset_repo):
        """Test getting all presets for a device."""
        # Set presets 1, 3, 5 for device123
        for preset_num in [1, 3, 5]:
            preset = Preset(
                device_id="device123",
                preset_number=preset_num,
                station_uuid=f"uuid-{preset_num}",
                station_name=f"Station {preset_num}",
                station_url=f"http://station{preset_num}.com/stream",
            )
            await preset_repo.set_preset(preset)

        # Set preset 2 for device456
        other_preset = Preset(
            device_id="device456",
            preset_number=2,
            station_uuid="uuid-other",
            station_name="Other Station",
            station_url="http://other.com/stream",
        )
        await preset_repo.set_preset(other_preset)

        result = await preset_repo.get_all_presets("device123")

        assert len(result) == 3
        preset_numbers = [p.preset_number for p in result]
        assert set(preset_numbers) == {1, 3, 5}
        # Verify they're sorted by preset_number
        assert preset_numbers == [1, 3, 5]

    @pytest.mark.asyncio
    async def test_clear_preset_existing(self, preset_repo, sample_preset_data):
        """Test clearing an existing preset."""
        preset = Preset(**sample_preset_data)
        await preset_repo.set_preset(preset)

        deleted_count = await preset_repo.clear_preset("device123", 1)

        assert deleted_count == 1

        # Verify preset is gone
        result = await preset_repo.get_preset("device123", 1)
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_preset_nonexistent(self, preset_repo):
        """Test clearing a nonexistent preset returns 0."""
        deleted_count = await preset_repo.clear_preset("nonexistent", 1)

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_clear_all_presets(self, preset_repo):
        """Test clearing all presets for a device."""
        # Set multiple presets for device123
        for preset_num in [1, 2, 3]:
            preset = Preset(
                device_id="device123",
                preset_number=preset_num,
                station_uuid=f"uuid-{preset_num}",
                station_name=f"Station {preset_num}",
                station_url=f"http://station{preset_num}.com/stream",
            )
            await preset_repo.set_preset(preset)

        # Set preset for device456 (should not be deleted)
        other_preset = Preset(
            device_id="device456",
            preset_number=1,
            station_uuid="uuid-other",
            station_name="Other",
            station_url="http://other.com/stream",
        )
        await preset_repo.set_preset(other_preset)

        deleted_count = await preset_repo.clear_all_presets("device123")

        assert deleted_count == 3

        # Verify device123 presets are gone
        result = await preset_repo.get_all_presets("device123")
        assert result == []

        # Verify device456 preset still exists
        result = await preset_repo.get_all_presets("device456")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_database_not_initialized_error(self):
        """Test that operations fail if database is not initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = PresetRepository(str(db_path))
            # Don't call initialize()

            preset = Preset(
                device_id="device",
                preset_number=1,
                station_uuid="uuid",
                station_name="Station",
                station_url="http://example.com",
            )

            with pytest.raises(RuntimeError, match="Database not initialized"):
                await repo.set_preset(preset)

    @pytest.mark.asyncio
    async def test_unique_constraint_device_preset_number(self, preset_repo):
        """Test that (device_id, preset_number) is unique."""
        preset1 = Preset(
            device_id="device123",
            preset_number=1,
            station_uuid="uuid1",
            station_name="Station 1",
            station_url="http://station1.com",
        )
        preset2 = Preset(
            device_id="device123",
            preset_number=1,
            station_uuid="uuid2",
            station_name="Station 2",
            station_url="http://station2.com",
        )

        # First insert should succeed
        await preset_repo.set_preset(preset1)

        # Second insert with same device_id+preset_number should update
        await preset_repo.set_preset(preset2)

        # Should update, not create duplicate
        all_presets = await preset_repo.get_all_presets("device123")
        assert len(all_presets) == 1
        assert all_presets[0].station_uuid == "uuid2"
