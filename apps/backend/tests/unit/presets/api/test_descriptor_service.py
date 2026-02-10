"""Tests for station descriptor service."""

import pytest
from unittest.mock import AsyncMock

from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.api.descriptor_service import StationDescriptorService


@pytest.fixture
def mock_preset_repo():
    """Mock PresetRepository for testing."""
    return AsyncMock()


@pytest.fixture
def descriptor_service(mock_preset_repo):
    """StationDescriptorService instance with mocked repository."""
    return StationDescriptorService(mock_preset_repo)


@pytest.fixture
def sample_preset():
    """Sample preset for testing."""
    return Preset(
        device_id="device123",
        preset_number=1,
        station_uuid="station-uuid-abc",
        station_name="Test Radio",
        station_url="http://test.radio/stream.mp3",
        station_homepage="https://test.radio",
        station_favicon="https://test.radio/favicon.ico",
    )


class TestStationDescriptorService:
    """Tests for StationDescriptorService."""

    @pytest.mark.asyncio
    async def test_get_descriptor_existing_preset(
        self, descriptor_service, mock_preset_repo, sample_preset
    ):
        """Test getting descriptor for existing preset."""
        mock_preset_repo.get_preset.return_value = sample_preset

        result = await descriptor_service.get_descriptor("device123", 1)

        assert result is not None
        assert result["stationName"] == "Test Radio"
        assert result["streamUrl"] == "http://test.radio/stream.mp3"
        assert result["homepage"] == "https://test.radio"
        assert result["favicon"] == "https://test.radio/favicon.ico"
        assert result["uuid"] == "station-uuid-abc"

        mock_preset_repo.get_preset.assert_called_once_with("device123", 1)

    @pytest.mark.asyncio
    async def test_get_descriptor_nonexistent_preset(
        self, descriptor_service, mock_preset_repo
    ):
        """Test getting descriptor for nonexistent preset returns None."""
        mock_preset_repo.get_preset.return_value = None

        result = await descriptor_service.get_descriptor("device123", 1)

        assert result is None
        mock_preset_repo.get_preset.assert_called_once_with("device123", 1)

    @pytest.mark.asyncio
    async def test_get_descriptor_with_none_optional_fields(
        self, descriptor_service, mock_preset_repo
    ):
        """Test descriptor with None optional fields."""
        preset = Preset(
            device_id="device123",
            preset_number=2,
            station_uuid="uuid",
            station_name="Minimal Station",
            station_url="http://minimal.com/stream",
            station_homepage=None,
            station_favicon=None,
        )
        mock_preset_repo.get_preset.return_value = preset

        result = await descriptor_service.get_descriptor("device123", 2)

        assert result is not None
        assert result["stationName"] == "Minimal Station"
        assert result["streamUrl"] == "http://minimal.com/stream"
        assert result["homepage"] is None
        assert result["favicon"] is None
        assert result["uuid"] == "uuid"

    @pytest.mark.asyncio
    async def test_get_descriptor_different_preset_numbers(
        self, descriptor_service, mock_preset_repo
    ):
        """Test descriptors for different preset numbers."""
        for preset_num in range(1, 7):
            preset = Preset(
                device_id="device123",
                preset_number=preset_num,
                station_uuid=f"uuid-{preset_num}",
                station_name=f"Station {preset_num}",
                station_url=f"http://station{preset_num}.com/stream",
            )
            mock_preset_repo.get_preset.return_value = preset

            result = await descriptor_service.get_descriptor("device123", preset_num)

            assert result is not None
            assert result["stationName"] == f"Station {preset_num}"
            assert result["uuid"] == f"uuid-{preset_num}"
