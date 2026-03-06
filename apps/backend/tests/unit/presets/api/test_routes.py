"""
Tests for preset management API routes (routes.py).

Covers error paths and happy paths for:
- POST  /api/presets/set            → set_preset
- GET   /api/presets/{device_id}    → get_device_presets
- GET   /api/presets/{device_id}/{preset_number} → get_preset
- DELETE /api/presets/{device_id}/{preset_number} → clear_preset
- DELETE /api/presets/{device_id}   → clear_all_presets
- POST  /api/presets/{device_id}/sync → sync_presets_from_device
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_preset_service
from opencloudtouch.main import app
from opencloudtouch.presets.models import Preset

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_preset(**overrides) -> Preset:
    """Create a Preset with default values, applying any overrides."""
    defaults: dict = dict(
        id=1,
        device_id="DEV1",
        preset_number=1,
        station_uuid="uuid-abc",
        station_name="Test Radio",
        station_url="http://stream.test/radio.mp3",
        station_homepage=None,
        station_favicon=None,
        source="INTERNET_RADIO",
    )
    # id is passed separately since the Preset constructor accepts it
    extra_id = overrides.pop("id", 1)
    defaults.update(overrides)
    preset = Preset(**{k: v for k, v in defaults.items() if k != "id"})
    preset.id = extra_id
    return preset


_SET_PAYLOAD = dict(
    device_id="DEV1",
    preset_number=1,
    station_uuid="uuid-abc",
    station_name="Test Radio",
    station_url="http://stream.test/radio.mp3",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_service():
    return AsyncMock()


@pytest.fixture
def client(mock_service):
    app.dependency_overrides[get_preset_service] = lambda: mock_service
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# set_preset
# ---------------------------------------------------------------------------


class TestSetPreset:
    """Tests for POST /api/presets/set."""

    def test_set_preset_returns_201_on_success(self, client, mock_service):
        mock_service.set_preset = AsyncMock(return_value=_make_preset())
        r = client.post("/api/presets/set", json=_SET_PAYLOAD)
        assert r.status_code == 201

    def test_set_preset_response_contains_station_name(self, client, mock_service):
        mock_service.set_preset = AsyncMock(return_value=_make_preset())
        r = client.post("/api/presets/set", json=_SET_PAYLOAD)
        assert r.json()["station_name"] == "Test Radio"

    def test_set_preset_returns_400_on_value_error(self, client, mock_service):
        """ValueError from service (bad preset number) → 400."""
        mock_service.set_preset = AsyncMock(
            side_effect=ValueError("Invalid preset_number: 0. Must be 1-6.")
        )
        r = client.post("/api/presets/set", json=_SET_PAYLOAD)
        assert r.status_code == 400

    def test_set_preset_returns_500_on_unexpected_error(self, client, mock_service):
        """Unexpected exception → 500."""
        mock_service.set_preset = AsyncMock(side_effect=RuntimeError("db error"))
        r = client.post("/api/presets/set", json=_SET_PAYLOAD)
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# get_device_presets
# ---------------------------------------------------------------------------


class TestGetDevicePresets:
    """Tests for GET /api/presets/{device_id}."""

    def test_returns_list_of_presets(self, client, mock_service):
        mock_service.get_all_presets = AsyncMock(
            return_value=[_make_preset(), _make_preset(preset_number=2, id=2)]
        )
        r = client.get("/api/presets/DEV1")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_returns_empty_list_when_no_presets(self, client, mock_service):
        mock_service.get_all_presets = AsyncMock(return_value=[])
        r = client.get("/api/presets/DEV1")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_500_on_unexpected_error(self, client, mock_service):
        """Unexpected exception → 500."""
        mock_service.get_all_presets = AsyncMock(side_effect=RuntimeError("db fail"))
        r = client.get("/api/presets/DEV1")
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# get_preset
# ---------------------------------------------------------------------------


class TestGetPreset:
    """Tests for GET /api/presets/{device_id}/{preset_number}."""

    def test_returns_preset_when_found(self, client, mock_service):
        mock_service.get_preset = AsyncMock(return_value=_make_preset())
        r = client.get("/api/presets/DEV1/1")
        assert r.status_code == 200
        assert r.json()["device_id"] == "DEV1"

    def test_returns_404_when_preset_not_found(self, client, mock_service):
        mock_service.get_preset = AsyncMock(return_value=None)
        r = client.get("/api/presets/DEV1/1")
        assert r.status_code == 404

    def test_returns_422_for_invalid_preset_number(self, client, mock_service):
        """Preset number outside 1-6 is rejected by FastAPI path validation."""
        r = client.get("/api/presets/DEV1/7")
        assert r.status_code == 422

    def test_returns_500_on_unexpected_error(self, client, mock_service):
        """Non-HTTPException → wrapped as 500."""
        mock_service.get_preset = AsyncMock(side_effect=RuntimeError("db crash"))
        r = client.get("/api/presets/DEV1/1")
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# clear_preset
# ---------------------------------------------------------------------------


class TestClearPreset:
    """Tests for DELETE /api/presets/{device_id}/{preset_number}."""

    def test_returns_200_and_message_when_deleted(self, client, mock_service):
        mock_service.clear_preset = AsyncMock(return_value=True)
        r = client.delete("/api/presets/DEV1/1")
        assert r.status_code == 200
        assert "message" in r.json()

    def test_returns_404_when_preset_not_found(self, client, mock_service):
        mock_service.clear_preset = AsyncMock(return_value=False)
        r = client.delete("/api/presets/DEV1/1")
        assert r.status_code == 404

    def test_returns_500_on_unexpected_error(self, client, mock_service):
        mock_service.clear_preset = AsyncMock(side_effect=RuntimeError("fail"))
        r = client.delete("/api/presets/DEV1/1")
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# clear_all_presets
# ---------------------------------------------------------------------------


class TestClearAllPresets:
    """Tests for DELETE /api/presets/{device_id}."""

    def test_returns_200_with_count_in_message(self, client, mock_service):
        mock_service.clear_all_presets = AsyncMock(return_value=3)
        r = client.delete("/api/presets/DEV1")
        assert r.status_code == 200
        assert "3" in r.json()["message"]

    def test_returns_200_when_no_presets_cleared(self, client, mock_service):
        mock_service.clear_all_presets = AsyncMock(return_value=0)
        r = client.delete("/api/presets/DEV1")
        assert r.status_code == 200
        assert "0" in r.json()["message"]

    def test_returns_500_on_unexpected_error(self, client, mock_service):
        mock_service.clear_all_presets = AsyncMock(side_effect=RuntimeError("fail"))
        r = client.delete("/api/presets/DEV1")
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# sync_presets_from_device
# ---------------------------------------------------------------------------


class TestSyncPresetsFromDevice:
    """Tests for POST /api/presets/{device_id}/sync."""

    def test_returns_200_with_synced_count(self, client, mock_service):
        mock_service.sync_presets_from_device = AsyncMock(return_value=4)
        r = client.post("/api/presets/DEV1/sync")
        assert r.status_code == 200
        assert "4" in r.json()["message"]

    def test_returns_404_when_device_not_found(self, client, mock_service):
        """ValueError from service (device not found) → 404."""
        mock_service.sync_presets_from_device = AsyncMock(
            side_effect=ValueError("Device DEV1 not found")
        )
        r = client.post("/api/presets/DEV1/sync")
        assert r.status_code == 404

    def test_returns_502_on_device_unreachable(self, client, mock_service):
        """Unexpected exception (device unreachable) → 502."""
        mock_service.sync_presets_from_device = AsyncMock(
            side_effect=RuntimeError("connection refused")
        )
        r = client.post("/api/presets/DEV1/sync")
        assert r.status_code == 502
