"""Integration tests for device API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from opencloudtouch.core.dependencies import set_settings_repo
from opencloudtouch.db import Device, DeviceRepository
from opencloudtouch.devices.client import DeviceInfo
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
    """Mock settings repository and register it."""
    mock_repo = AsyncMock(spec=SettingsRepository)
    mock_repo.get_manual_ips = AsyncMock(return_value=[])
    set_settings_repo(mock_repo)
    yield mock_repo


@pytest.mark.asyncio
async def test_discover_endpoint_success(mock_config, mock_settings_repo):
    """Test /api/devices/discover endpoint with successful discovery."""
    discovered = [
        DiscoveredDevice(ip="192.168.1.100", port=8090, name="Living Room"),
        DiscoveredDevice(ip="192.168.1.101", port=8090, name="Kitchen"),
    ]

    with patch(
        "opencloudtouch.devices.api.routes.BoseDeviceDiscoveryAdapter"
    ) as mock_adapter:
        mock_instance = AsyncMock()
        mock_instance.discover.return_value = discovered
        mock_adapter.return_value = mock_instance

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/discover")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["devices"]) == 2
        assert data["devices"][0]["ip"] == "192.168.1.100"


@pytest.mark.asyncio
async def test_discover_endpoint_with_manual_ips(mock_config, mock_settings_repo):
    """Test discovery with manual IPs configured."""
    mock_config.discovery_enabled = False
    mock_config.manual_device_ips_list = ["192.168.1.200"]

    manual_discovered = [
        DiscoveredDevice(ip="192.168.1.200", port=8090, name="Manual Device")
    ]

    with patch("opencloudtouch.devices.api.routes.ManualDiscovery") as mock_manual:
        mock_instance = AsyncMock()
        mock_instance.discover.return_value = manual_discovered
        mock_manual.return_value = mock_instance

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/discover")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["devices"][0]["ip"] == "192.168.1.200"


@pytest.mark.asyncio
async def test_discover_endpoint_no_devices(mock_config, mock_settings_repo):
    """Test discovery when no devices are found."""
    with patch(
        "opencloudtouch.devices.api.routes.BoseDeviceDiscoveryAdapter"
    ) as mock_adapter:
        mock_instance = AsyncMock()
        mock_instance.discover.return_value = []
        mock_adapter.return_value = mock_instance

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/discover")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["devices"] == []


@pytest.mark.asyncio
async def test_discover_endpoint_discovery_error(mock_config, mock_settings_repo):
    """Test discovery endpoint when discovery fails."""
    with patch(
        "opencloudtouch.devices.api.routes.BoseDeviceDiscoveryAdapter"
    ) as mock_adapter:
        mock_instance = AsyncMock()
        mock_instance.discover.side_effect = Exception("Network error")
        mock_adapter.return_value = mock_instance

        # Discovery errors are caught and logged, returns empty list
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/discover")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0


@pytest.mark.asyncio
async def test_sync_devices_success(mock_config, mock_settings_repo):
    """Test /api/devices/sync endpoint with successful sync."""
    discovered = [DiscoveredDevice(ip="192.168.1.100", port=8090, name="Living Room")]

    device_info = DeviceInfo(
        device_id="AABBCC112233",
        name="Living Room",
        type="SoundTouch 10",
        mac_address="AA:BB:CC:11:22:33",
        ip_address="192.168.1.100",
        firmware_version="1.0.0",
    )

    # Mock repository
    mock_repo = AsyncMock(spec=DeviceRepository)
    mock_repo.upsert = AsyncMock()

    async def get_mock_repo():
        return mock_repo

    try:
        with patch(
            "opencloudtouch.devices.services.sync_service.get_discovery_adapter"
        ) as mock_get_disco, patch(
            "opencloudtouch.devices.services.sync_service.get_device_client"
        ) as mock_get_client:

            # Mock discovery factory
            mock_disco_instance = AsyncMock()
            mock_disco_instance.discover.return_value = discovered
            mock_get_disco.return_value = mock_disco_instance

            # Mock client factory
            mock_client_instance = AsyncMock()
            mock_client_instance.get_info.return_value = device_info
            mock_get_client.return_value = mock_client_instance

            # Override dependency
            from opencloudtouch.devices.api.routes import get_device_repo

            app.dependency_overrides[get_device_repo] = get_mock_repo

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
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
    discovered = [
        DiscoveredDevice(ip="192.168.1.100", port=8090, name="Working"),
        DiscoveredDevice(ip="192.168.1.101", port=8090, name="Broken"),
    ]

    device_info = DeviceInfo(
        device_id="AABBCC112233",
        name="Working",
        type="SoundTouch 10",
        mac_address="AA:BB:CC:11:22:33",
        ip_address="192.168.1.100",
        firmware_version="1.0.0",
    )

    mock_repo = AsyncMock(spec=DeviceRepository)
    mock_repo.upsert = AsyncMock()

    async def get_mock_repo():
        return mock_repo

    try:
        with patch(
            "opencloudtouch.devices.services.sync_service.get_discovery_adapter"
        ) as mock_get_disco, patch(
            "opencloudtouch.devices.services.sync_service.get_device_client"
        ) as mock_get_client:

            mock_disco_instance = AsyncMock()
            mock_disco_instance.discover.return_value = discovered
            mock_get_disco.return_value = mock_disco_instance

            # First device succeeds, second fails
            mock_client_instance = AsyncMock()
            mock_client_instance.get_info.side_effect = [
                device_info,
                Exception("Connection timeout"),
            ]
            mock_get_client.return_value = mock_client_instance

            from opencloudtouch.devices.api.routes import get_device_repo

            app.dependency_overrides[get_device_repo] = get_mock_repo

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
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
    from opencloudtouch.devices.api.routes import get_device_repo

    mock_repo = AsyncMock(spec=DeviceRepository)
    mock_repo.get_all.return_value = []

    async def get_mock_repo():
        return mock_repo

    app.dependency_overrides[get_device_repo] = get_mock_repo

    try:
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
    from opencloudtouch.devices.api.routes import get_device_repo

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

    mock_repo = AsyncMock(spec=DeviceRepository)
    mock_repo.get_all.return_value = devices

    async def get_mock_repo():
        return mock_repo

    app.dependency_overrides[get_device_repo] = get_mock_repo

    try:
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
    from opencloudtouch.devices.api.routes import get_device_repo

    device = Device(
        device_id="DEVICE1",
        ip="192.168.1.100",
        name="Living Room",
        model="SoundTouch 10",
        mac_address="AA:BB:CC:11:22:33",
        firmware_version="1.0.0",
    )

    mock_repo = AsyncMock(spec=DeviceRepository)
    mock_repo.get_by_device_id.return_value = device

    async def get_mock_repo():
        return mock_repo

    app.dependency_overrides[get_device_repo] = get_mock_repo

    try:
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
    from opencloudtouch.devices.api.routes import get_device_repo

    mock_repo = AsyncMock(spec=DeviceRepository)
    mock_repo.get_by_device_id.return_value = None

    async def get_mock_repo():
        return mock_repo

    app.dependency_overrides[get_device_repo] = get_mock_repo

    try:
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
    """
    # Manual IP configured in database (via API)
    db_manual_ip = "192.168.178.78"

    # Mock settings repo to return DB IP
    mock_settings = AsyncMock(spec=SettingsRepository)
    mock_settings.get_manual_ips = AsyncMock(return_value=[db_manual_ip])
    set_settings_repo(mock_settings)

    # Mock config with EMPTY ENV vars
    with patch("opencloudtouch.devices.api.routes.get_config") as mock_get_cfg:
        mock_cfg = AsyncMock()
        mock_cfg.discovery_enabled = True
        mock_cfg.discovery_timeout = 5
        mock_cfg.manual_device_ips_list = []  # ← No ENV IPs!
        mock_get_cfg.return_value = mock_cfg

        # Mock device repository
        mock_repo = AsyncMock(spec=DeviceRepository)
        mock_repo.upsert = AsyncMock()

        async def get_mock_repo():
            return mock_repo

        # Mock discovery and client
        device_info = DeviceInfo(
            device_id="TEST123",
            name="Test Device",
            type="SoundTouch 10",
            mac_address="AA:BB:CC:DD:EE:FF",
            ip_address=db_manual_ip,
            firmware_version="1.0.0",
        )

        try:
            with patch(
                "opencloudtouch.devices.services.sync_service.get_discovery_adapter"
            ) as mock_get_disco, patch(
                "opencloudtouch.devices.services.sync_service.get_device_client"
            ) as mock_get_client, patch(
                "opencloudtouch.devices.services.sync_service.ManualDiscovery"
            ) as mock_manual_disco:

                # SSDP discovery returns empty
                mock_ssdp_instance = AsyncMock()
                mock_ssdp_instance.discover.return_value = []
                mock_get_disco.return_value = mock_ssdp_instance

                # Manual discovery returns device from DB IP
                mock_manual_instance = AsyncMock()
                mock_manual_instance.discover.return_value = [
                    DiscoveredDevice(
                        ip=db_manual_ip,
                        port=8090,
                        name="Test Device",
                        model="SoundTouch 10",
                    )
                ]
                mock_manual_disco.return_value = mock_manual_instance

                # Device client returns info
                mock_client_instance = AsyncMock()
                mock_client_instance.get_info.return_value = device_info
                mock_get_client.return_value = mock_client_instance

                # Override repo dependency
                from opencloudtouch.devices.api.routes import get_device_repo

                app.dependency_overrides[get_device_repo] = get_mock_repo

                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post("/api/devices/sync")

                assert response.status_code == 200
                data = response.json()

                # CRITICAL: Must discover 1 device (from DB manual IP)
                assert (
                    data["discovered"] == 1
                ), f"Expected 1 device from DB manual IP, got {data['discovered']}"
                assert data["synced"] == 1

                # Verify ManualDiscovery was called with DB IP
                mock_manual_disco.assert_called_once_with([db_manual_ip])

                # Verify device was persisted
                mock_repo.upsert.assert_called_once()

        finally:
            app.dependency_overrides.clear()
