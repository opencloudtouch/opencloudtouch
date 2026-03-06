"""Unit tests for presets/api/station_routes.py HTTP endpoints.

Covers the HTTP layer of station descriptor serving:
- 200 success path
- 404 when preset not configured
- 500 generic exception path (lines 78-82)
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_preset_service
from opencloudtouch.main import app


@pytest.fixture
def mock_preset_service():
    """Mock PresetService."""
    return AsyncMock()


@pytest.fixture
def client(mock_preset_service):
    """FastAPI test client with injected mock PresetService."""
    app.dependency_overrides[get_preset_service] = lambda: mock_preset_service
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestStationDescriptorEndpoint:
    """Tests for GET /stations/preset/{device_id}/{preset_number}.json."""

    def test_returns_descriptor_when_preset_exists(self, client, mock_preset_service):
        """Returns 200 with descriptor when preset is configured."""
        from opencloudtouch.presets.models import Preset

        mock_preset_service.get_preset = AsyncMock(
            return_value=Preset(
                device_id="DEV123",
                preset_number=1,
                station_uuid="uuid-001",
                station_name="Test Radio",
                station_url="http://stream.example.com/radio.mp3",
            )
        )

        response = client.get("/stations/preset/DEV123/1.json")

        assert response.status_code == 200
        data = response.json()
        assert data["stationName"] == "Test Radio"

    def test_returns_404_when_preset_not_configured(self, client, mock_preset_service):
        """Returns 404 when no preset is configured for the device/number.

        Note: The SPA 404 handler in main.py intercepts all /stations/ 404s and
        formats the detail as "The requested resource {path} was not found".
        """
        mock_preset_service.get_preset = AsyncMock(return_value=None)

        response = client.get("/stations/preset/DEV123/3.json")

        assert response.status_code == 404
        assert "/stations/preset/DEV123/3.json" in response.json()["detail"]

    def test_returns_500_on_unexpected_exception(self, client, mock_preset_service):
        """Returns 500 on generic runtime error (covers lines 78-82).

        Regression: Unhandled exceptions should not leak stack traces to clients.
        """
        mock_preset_service.get_preset = AsyncMock(
            side_effect=RuntimeError("Database connection lost")
        )

        response = client.get("/stations/preset/DEV123/2.json")

        assert response.status_code == 500
        assert "station descriptor" in response.json()["detail"].lower()
