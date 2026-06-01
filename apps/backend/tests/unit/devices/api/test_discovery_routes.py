"""Unit tests for device discovery routes (extracted from routes.py in STORY-307).

Tests discovery-specific endpoints in isolation using discovery_router.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from opencloudtouch.devices.api.discovery_routes import (  # noqa: E402
    discovery_router,
    _discovery_lock,
)
from opencloudtouch.core.dependencies import get_device_service, get_settings_service
from opencloudtouch.devices.repository import Device


@pytest.fixture
def mock_device_service():
    service = AsyncMock()
    return service


@pytest.fixture
def mock_settings_service():
    service = AsyncMock()
    service.get_manual_ips = AsyncMock(return_value=[])
    service.set_manual_ips = AsyncMock()
    return service


@pytest.fixture
def app(mock_device_service, mock_settings_service):
    application = FastAPI()
    application.include_router(discovery_router)
    application.dependency_overrides[get_device_service] = lambda: mock_device_service
    application.dependency_overrides[get_settings_service] = (
        lambda: mock_settings_service
    )
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def sample_device():
    return Device(
        device_id="AABBCC112233",
        ip="192.168.1.100",
        name="Living Room",
        model="SoundTouch 30",
        mac_address="AA:BB:CC:11:22:33",
        firmware_version="28.0.3.46454",
    )


class TestDiscoveryRouterImport:
    """Verify the discovery_router is importable and functional."""

    def test_discovery_lock_exported(self):
        """_discovery_lock is exported from discovery_routes."""
        import asyncio

        assert isinstance(_discovery_lock, asyncio.Lock)

    def test_discover_endpoint_returns_200(self, client, mock_device_service):
        """GET /api/devices/discover returns 200 with empty device list."""
        mock_device_service.discover_devices = AsyncMock(return_value=[])

        response = client.get("/api/devices/discover")

        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_sync_endpoint_returns_409_when_locked(self, client):
        """POST /api/devices/sync returns 409 when discovery lock is held."""
        from opencloudtouch.devices.api.discovery_routes import _discovery_lock

        with patch.object(_discovery_lock, "locked", return_value=True):
            response = client.post("/api/devices/sync")

        assert response.status_code == 409


class TestProbeEndpoint:
    """Tests for POST /api/devices/probe."""

    def test_probe_valid_ip_returns_device(
        self, client, mock_device_service, mock_settings_service, sample_device
    ):
        """Probe with valid IP returns device data."""
        mock_device_service.probe_single_device = AsyncMock(return_value=sample_device)

        response = client.post(
            "/api/devices/probe",
            json={"ip": "192.168.1.100"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["device_id"] == "AABBCC112233"
        assert data["ip"] == "192.168.1.100"
        assert data["name"] == "Living Room"
        assert data["model"] == "SoundTouch 30"
        mock_device_service.probe_single_device.assert_called_once_with("192.168.1.100")

    def test_probe_adds_ip_to_manual_ips(
        self, client, mock_device_service, mock_settings_service, sample_device
    ):
        """Probe adds IP to manual IPs list when not already present."""
        mock_device_service.probe_single_device = AsyncMock(return_value=sample_device)
        mock_settings_service.get_manual_ips.return_value = ["10.0.0.1"]

        client.post("/api/devices/probe", json={"ip": "192.168.1.100"})

        mock_settings_service.set_manual_ips.assert_called_once_with(
            ["10.0.0.1", "192.168.1.100"]
        )

    def test_probe_skips_duplicate_ip(
        self, client, mock_device_service, mock_settings_service, sample_device
    ):
        """Probe does not add IP if already in manual IPs."""
        mock_device_service.probe_single_device = AsyncMock(return_value=sample_device)
        mock_settings_service.get_manual_ips.return_value = ["192.168.1.100"]

        client.post("/api/devices/probe", json={"ip": "192.168.1.100"})

        mock_settings_service.set_manual_ips.assert_not_called()

    def test_probe_invalid_ip_returns_422(self, client):
        """Probe with invalid IP returns 422."""
        response = client.post(
            "/api/devices/probe",
            json={"ip": "not-an-ip"},
        )

        assert response.status_code == 422
        assert "Invalid IP address format" in response.json()["detail"]

    def test_probe_unreachable_device_returns_404(self, client, mock_device_service):
        """Probe returns 404 when device is not reachable."""
        mock_device_service.probe_single_device = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        response = client.post(
            "/api/devices/probe",
            json={"ip": "192.168.1.200"},
        )

        assert response.status_code == 404
        assert "not reachable" in response.json()["detail"]

    def test_probe_strips_whitespace_from_ip(
        self, client, mock_device_service, mock_settings_service, sample_device
    ):
        """Probe strips whitespace from IP."""
        mock_device_service.probe_single_device = AsyncMock(return_value=sample_device)

        response = client.post(
            "/api/devices/probe",
            json={"ip": "  192.168.1.100  "},
        )

        assert response.status_code == 200
        mock_device_service.probe_single_device.assert_called_once_with("192.168.1.100")

    def test_probe_settings_error_does_not_fail_request(
        self, client, mock_device_service, mock_settings_service, sample_device
    ):
        """If saving manual IP fails, the probe still succeeds."""
        mock_device_service.probe_single_device = AsyncMock(return_value=sample_device)
        mock_settings_service.get_manual_ips.side_effect = Exception("DB error")

        response = client.post(
            "/api/devices/probe",
            json={"ip": "192.168.1.100"},
        )

        assert response.status_code == 200
        assert response.json()["device_id"] == "AABBCC112233"
