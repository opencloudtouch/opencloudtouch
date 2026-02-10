"""Tests for preset domain models."""

from datetime import datetime, UTC
import pytest
from opencloudtouch.presets.models import Preset


class TestPresetModel:
    """Tests for Preset domain model."""

    def test_preset_creation_minimal(self):
        """Test creating preset with minimal required fields."""
        preset = Preset(
            device_id="abc123",
            preset_number=1,
            station_uuid="station-uuid-123",
            station_name="Test Station",
            station_url="http://example.com/stream.mp3",
        )

        assert preset.device_id == "abc123"
        assert preset.preset_number == 1
        assert preset.station_uuid == "station-uuid-123"
        assert preset.station_name == "Test Station"
        assert preset.station_url == "http://example.com/stream.mp3"
        assert preset.station_homepage is None
        assert preset.station_favicon is None
        assert preset.id is None
        assert isinstance(preset.created_at, datetime)
        assert isinstance(preset.updated_at, datetime)

    def test_preset_creation_full(self):
        """Test creating preset with all fields."""
        now = datetime.now(UTC)
        preset = Preset(
            device_id="abc123",
            preset_number=3,
            station_uuid="station-uuid-456",
            station_name="Jazz Radio",
            station_url="http://jazz.example.com/stream",
            station_homepage="https://jazz.example.com",
            station_favicon="https://jazz.example.com/favicon.ico",
            created_at=now,
            updated_at=now,
            id=42,
        )

        assert preset.id == 42
        assert preset.device_id == "abc123"
        assert preset.preset_number == 3
        assert preset.station_homepage == "https://jazz.example.com"
        assert preset.station_favicon == "https://jazz.example.com/favicon.ico"
        assert preset.created_at == now
        assert preset.updated_at == now

    def test_preset_number_validation_too_low(self):
        """Test that preset_number < 1 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid preset_number: 0"):
            Preset(
                device_id="abc123",
                preset_number=0,
                station_uuid="uuid",
                station_name="Station",
                station_url="http://example.com/stream",
            )

    def test_preset_number_validation_too_high(self):
        """Test that preset_number > 6 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid preset_number: 7"):
            Preset(
                device_id="abc123",
                preset_number=7,
                station_uuid="uuid",
                station_name="Station",
                station_url="http://example.com/stream",
            )

    def test_preset_number_validation_boundary_values(self):
        """Test that preset_number 1 and 6 are valid."""
        # Lower boundary
        preset1 = Preset(
            device_id="abc",
            preset_number=1,
            station_uuid="uuid",
            station_name="Station",
            station_url="http://example.com",
        )
        assert preset1.preset_number == 1

        # Upper boundary
        preset6 = Preset(
            device_id="abc",
            preset_number=6,
            station_uuid="uuid",
            station_name="Station",
            station_url="http://example.com",
        )
        assert preset6.preset_number == 6

    def test_to_dict(self):
        """Test conversion to dictionary."""
        now = datetime.now(UTC)
        preset = Preset(
            device_id="device123",
            preset_number=2,
            station_uuid="station-uuid",
            station_name="Rock FM",
            station_url="http://rock.fm/stream",
            station_homepage="https://rock.fm",
            station_favicon="https://rock.fm/icon.png",
            created_at=now,
            updated_at=now,
            id=10,
        )

        result = preset.to_dict()

        assert result["id"] == 10
        assert result["device_id"] == "device123"
        assert result["preset_number"] == 2
        assert result["station_uuid"] == "station-uuid"
        assert result["station_name"] == "Rock FM"
        assert result["station_url"] == "http://rock.fm/stream"
        assert result["station_homepage"] == "https://rock.fm"
        assert result["station_favicon"] == "https://rock.fm/icon.png"
        assert result["created_at"] == now.isoformat()
        assert result["updated_at"] == now.isoformat()

    def test_to_dict_with_none_values(self):
        """Test to_dict with optional None values."""
        preset = Preset(
            device_id="device123",
            preset_number=4,
            station_uuid="uuid",
            station_name="Station",
            station_url="http://example.com",
        )

        result = preset.to_dict()

        assert result["id"] is None
        assert result["station_homepage"] is None
        assert result["station_favicon"] is None
        assert result["created_at"] is not None  # Auto-set
        assert result["updated_at"] is not None  # Auto-set

    def test_repr(self):
        """Test string representation."""
        preset = Preset(
            device_id="device123",
            preset_number=5,
            station_uuid="uuid",
            station_name="Classical Radio",
            station_url="http://classical.com/stream",
        )

        repr_str = repr(preset)

        assert "Preset(" in repr_str
        assert "device_id='device123'" in repr_str
        assert "preset_number=5" in repr_str
        assert "station_name='Classical Radio'" in repr_str
