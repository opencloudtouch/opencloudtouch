"""Integration tests for device API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from opencloudtouch.db import Device
from opencloudtouch.discovery import DiscoveredDevice
from opencloudtouch.main import app
from opencloudtouch.settings.repository import SettingsRepository


@pytest.fixture
def mock_config():
    """Mock configuration."""
    with patch("opencloudtouch.devices.api.routes.get_config") as mock:
        mock_cfg = AsyncMock()
        mock_cfg.discovery_enabled = True
        mock_cfg.discovery_timeout = 5
        mock_cfg.manual_device_ips_list = []
        mock.return_value = mock_cfg
        yield mock_cfg


@pytest.fixture
def mock_settings_repo():
    """Mock settings repository and register it in app.state."""
    mock_repo = AsyncMock(spec=SettingsRepository)
    mock_repo.get_manual_ips = AsyncMock(return_value=[])
    app.state.settings_repo = mock_repo
    yield mock_repo


@pytest.mark.asyncio
async def test_discover_endpoint_success(mock_config, mock_settings_repo):
    """Test /api/devices/discover endpoint with successful discovery."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    discovered = [
        DiscoveredDevice(ip="192.168.1.100", port=8090, name="Living Room"),
        DiscoveredDevice(ip="192.168.1.101", port=8090, name="Kitchen"),
    ]

    # Mock DeviceService
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.discover_devices.return_value = discovered

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/discover")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["devices"]) == 2
        assert data["devices"][0]["ip"] == "192.168.1.100"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_discover_endpoint_with_manual_ips(mock_config, mock_settings_repo):
    """Test discovery with manual IPs configured."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    manual_discovered = [
        DiscoveredDevice(ip="192.168.1.200", port=8090, name="Manual Device")
    ]

    # Mock DeviceService
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.discover_devices.return_value = manual_discovered

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/discover")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["devices"][0]["ip"] == "192.168.1.200"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_discover_endpoint_no_devices(mock_config, mock_settings_repo):
    """Test discovery when no devices are found."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    # Mock DeviceService returning empty list
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.discover_devices.return_value = []

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/discover")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["devices"] == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_discover_endpoint_discovery_error(mock_config, mock_settings_repo):
    """Test discovery endpoint when discovery fails."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    # Mock DeviceService raising exception
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.discover_devices.side_effect = Exception("Network error")

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/discover")

        # Route catches exception and returns 500
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_devices_success(mock_config, mock_settings_repo):
    """Test /api/devices/sync endpoint with successful sync."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService
    from opencloudtouch.devices.models import SyncResult

    # Mock DeviceService
    mock_service = AsyncMock(spec=DeviceService)
    sync_result = SyncResult(discovered=1, synced=1, failed=0)
    mock_service.sync_devices.return_value = sync_result

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/devices/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["discovered"] == 1
        assert data["synced"] == 1
        assert data["failed"] == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_devices_partial_failure(mock_config, mock_settings_repo):
    """Test sync with one device failing to connect."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService
    from opencloudtouch.devices.models import SyncResult

    # Mock DeviceService with partial failure
    mock_service = AsyncMock(spec=DeviceService)
    sync_result = SyncResult(discovered=2, synced=1, failed=1)
    mock_service.sync_devices.return_value = sync_result

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/devices/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["discovered"] == 2
        assert data["synced"] == 1
        assert data["failed"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_devices_empty():
    """Test GET /api/devices with no devices in DB."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    # Mock DeviceService returning empty list
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.get_all_devices.return_value = []

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["devices"] == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_devices_with_data():
    """Test GET /api/devices with devices in DB."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    devices = [
        Device(
            device_id="DEVICE1",
            ip="192.168.1.100",
            name="Living Room",
            model="SoundTouch 10",
            mac_address="AA:BB:CC:11:22:33",
            firmware_version="1.0.0",
        ),
        Device(
            device_id="DEVICE2",
            ip="192.168.1.101",
            name="Kitchen",
            model="SoundTouch 20",
            mac_address="DD:EE:FF:44:55:66",
            firmware_version="1.0.1",
        ),
    ]

    # Mock DeviceService
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.get_all_devices.return_value = devices

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["devices"]) == 2
        assert data["devices"][0]["device_id"] == "DEVICE1"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_device_by_id_success():
    """Test GET /api/devices/{device_id} with existing device."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    device = Device(
        device_id="DEVICE1",
        ip="192.168.1.100",
        name="Living Room",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:11:22:33",
        firmware_version="1.0.0",
    )

    # Mock DeviceService
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.get_device_by_id.return_value = device

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/DEVICE1")

        assert response.status_code == 200
        data = response.json()
        assert data["device_id"] == "DEVICE1"
        assert data["name"] == "Living Room"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_device_by_id_not_found():
    """Test GET /api/devices/{device_id} with non-existent device."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    # Mock DeviceService returning None
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.get_device_by_id.return_value = None

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/NONEXISTENT")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_uses_manual_ips_from_database():
    """
    Regression test: /sync must use manual IPs from database, not just ENV vars.

    Bug: /sync only used config.manual_device_ips_list (ENV vars),
         ignoring manual IPs stored in database via POST /api/settings/manual-ips.
    Fixed: 2025-01-XX - /sync now merges DB + ENV IPs before discovery.

    Note: This integration test verifies the HTTP endpoint returns expected results.
    Internal details (how DeviceService gets manual IPs) are tested in unit tests.
    """
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService
    from opencloudtouch.devices.models import SyncResult

    # Manual IP configured in database (via API)
    db_manual_ip = "192.168.178.78"

    # Mock settings repo to return DB IP
    mock_settings = AsyncMock(spec=SettingsRepository)
    mock_settings.get_manual_ips = AsyncMock(return_value=[db_manual_ip])
    app.state.settings_repo = mock_settings

    # Mock DeviceService to return successful sync
    mock_service = AsyncMock(spec=DeviceService)
    sync_result = SyncResult(discovered=1, synced=1, failed=0)
    mock_service.sync_devices.return_value = sync_result

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/devices/sync")

        assert response.status_code == 200
        data = response.json()

        # CRITICAL: Must discover 1 device (from DB manual IP)
        assert (
            data["discovered"] == 1
        ), f"Expected 1 device from DB manual IP, got {data['discovered']}"
        assert data["synced"] == 1
        assert data["failed"] == 0

    finally:
        app.dependency_overrides.clear()
