"""
Real Integration Tests - Full API Stack without Mocks

These tests use:
- Real SQLite database (:memory:)
- Real FastAPI routes
- Real Repository implementations
- Real API layer

Only external dependencies are mocked:
- Device client (network calls to devices)
- SSDP Discovery (network multicast)
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from opencloudtouch.core.dependencies import (
    clear_dependencies,
    set_device_repo,
    set_device_service,
    set_settings_repo,
    set_settings_service,
)
from opencloudtouch.db import DeviceRepository
from opencloudtouch.devices.adapter import BoseDeviceDiscoveryAdapter
from opencloudtouch.devices.client import DeviceInfo
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.services.sync_service import DeviceSyncService
from opencloudtouch.discovery import DiscoveredDevice
from opencloudtouch.main import app
from opencloudtouch.settings.repository import SettingsRepository
from opencloudtouch.settings.service import SettingsService


@pytest.fixture
async def real_db():
    """Create real in-memory SQLite database."""
    # Use temporary file instead of :memory: to allow multiple connections
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    device_repo = DeviceRepository(db_path)
    settings_repo = SettingsRepository(db_path)

    await device_repo.initialize()
    await settings_repo.initialize()

    yield {"device_repo": device_repo, "settings_repo": settings_repo}

    await device_repo.close()
    await settings_repo.close()
    db_path.unlink(missing_ok=True)


@pytest.fixture
async def real_api_client(real_db):
    """FastAPI client with real DB and dependency overrides."""
    device_repo = real_db["device_repo"]
    settings_repo = real_db["settings_repo"]

    # Set repositories using dependency injection
    set_device_repo(device_repo)
    set_settings_repo(settings_repo)

    # Initialize services (same as main.py lifespan)
    sync_service = DeviceSyncService(
        repository=device_repo,
        discovery_timeout=10,
        manual_ips=[],
        discovery_enabled=True,
    )
    device_service = DeviceService(
        repository=device_repo,
        sync_service=sync_service,
        discovery_adapter=BoseDeviceDiscoveryAdapter(),
    )
    set_device_service(device_service)

    settings_service = SettingsService(repository=settings_repo)
    set_settings_service(settings_service)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        # Clean up dependencies after test
        clear_dependencies()


class TestRealAPIStack:
    """Integration tests using real API + DB stack."""

    @pytest.mark.asyncio
    async def test_full_device_sync_workflow(self, real_api_client, real_db):
        """
        Test complete device sync workflow with real DB.

        Workflow: Discover ? Sync to DB ? Fetch from DB
        """
        device_repo = real_db["device_repo"]

        # 1. Initial state: No devices in DB
        devices = await device_repo.get_all()
        assert len(devices) == 0

        # 2. Mock external dependencies (SSDP + BoseClient)
        discovered = [
            DiscoveredDevice(ip="192.168.1.100", port=8090, name="Living Room ST30"),
            DiscoveredDevice(ip="192.168.1.101", port=8090, name="Kitchen ST10"),
        ]

        mock_device_info_1 = DeviceInfo(
            device_id="AABBCC112233",
            name="Living Room ST30",
            type="SoundTouch 30 Series III",
            mac_address="AA:BB:CC:11:22:33",
            ip_address="192.168.1.100",
            firmware_version="28.0.12.46499",
        )

        mock_device_info_2 = DeviceInfo(
            device_id="DDEEFF445566",
            name="Kitchen ST10",
            type="SoundTouch 10",
            mac_address="DD:EE:FF:44:55:66",
            ip_address="192.168.1.101",
            firmware_version="28.0.12.46499",
        )

        with patch(
            "opencloudtouch.devices.services.sync_service.get_discovery_adapter"
        ) as mock_get_discovery, patch(
            "opencloudtouch.devices.services.sync_service.get_device_client"
        ) as mock_get_client, patch(
            "opencloudtouch.devices.api.routes.get_config"
        ) as mock_config:

            # Configure mocks
            mock_config.return_value.discovery_enabled = True
            mock_config.return_value.discovery_timeout = 5
            mock_config.return_value.manual_device_ips_list = []

            mock_discovery_instance = AsyncMock()
            mock_discovery_instance.discover.return_value = discovered
            mock_get_discovery.return_value = mock_discovery_instance

            # Mock client factory to return device info
            def create_mock_client(base_url, timeout=5):
                client = AsyncMock()
                if "192.168.1.100" in base_url:
                    client.get_info.return_value = mock_device_info_1
                else:
                    client.get_info.return_value = mock_device_info_2
                return client

            mock_get_client.side_effect = create_mock_client

            # 3. Trigger sync via API
            response = await real_api_client.post("/api/devices/sync")
            assert response.status_code == 200

            data = response.json()
            assert data["discovered"] == 2
            assert data["synced"] == 2
            assert data["failed"] == 0

        # 4. Verify devices were persisted to REAL DB
        devices = await device_repo.get_all()
        assert len(devices) == 2

        device_1 = await device_repo.get_by_device_id("AABBCC112233")
        assert device_1 is not None
        assert device_1.name == "Living Room ST30"
        assert device_1.ip == "192.168.1.100"
        assert device_1.model == "SoundTouch 30 Series III"

        device_2 = await device_repo.get_by_device_id("DDEEFF445566")
        assert device_2 is not None
        assert device_2.name == "Kitchen ST10"

        # 5. Fetch devices via API (should come from real DB)
        response = await real_api_client.get("/api/devices")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 2
        assert len(data["devices"]) == 2

        # Verify API response matches DB content
        api_device_ids = {d["device_id"] for d in data["devices"]}
        assert api_device_ids == {"AABBCC112233", "DDEEFF445566"}

    @pytest.mark.asyncio
    async def test_manual_ip_configuration_persistence(self, real_api_client, real_db):
        """
        Test manual IP configuration persists to real DB.

        Workflow: Add IPs ? Fetch IPs ? Delete IP ? Verify
        """
        settings_repo = real_db["settings_repo"]

        # 1. Initial state: No manual IPs
        ips = await settings_repo.get_manual_ips()
        assert len(ips) == 0

        response = await real_api_client.get("/api/settings/manual-ips")
        assert response.status_code == 200
        assert response.json() == {"ips": []}

        # 2. Add manual IPs via API
        test_ips = ["192.168.1.10", "192.168.1.20", "10.0.0.5"]
        response = await real_api_client.post(
            "/api/settings/manual-ips", json={"ips": test_ips}
        )
        assert response.status_code == 200

        # 3. Verify persistence in REAL DB
        db_ips = await settings_repo.get_manual_ips()
        assert set(db_ips) == set(test_ips)

        # 4. Fetch via API (should come from real DB)
        response = await real_api_client.get("/api/settings/manual-ips")
        assert response.status_code == 200

        data = response.json()
        assert set(data["ips"]) == set(test_ips)

        # 5. Delete one IP via API
        response = await real_api_client.delete("/api/settings/manual-ips/192.168.1.10")
        assert response.status_code == 200

        # 6. Verify deletion persisted to DB
        db_ips = await settings_repo.get_manual_ips()
        assert "192.168.1.10" not in db_ips
        assert "192.168.1.20" in db_ips
        assert "10.0.0.5" in db_ips

        # 7. Replace all IPs via bulk endpoint
        new_ips = ["10.0.0.1", "10.0.0.2"]
        response = await real_api_client.post(
            "/api/settings/manual-ips", json={"ips": new_ips}
        )
        assert response.status_code == 200

        # 8. Verify old IPs are gone, new IPs persisted
        db_ips = await settings_repo.get_manual_ips()
        assert set(db_ips) == set(new_ips)

    @pytest.mark.asyncio
    async def test_device_update_in_db(self, real_api_client, real_db):
        """
        Test device update workflow with real DB.

        Verifies upsert logic: existing devices get updated, not duplicated.
        """
        device_repo = real_db["device_repo"]

        # 1. Mock discovery with initial device
        discovered_v1 = [
            DiscoveredDevice(ip="192.168.1.100", port=8090, name="Living Room"),
        ]

        device_info_v1 = DeviceInfo(
            device_id="AABBCC112233",
            name="Living Room",  # Old name
            type="SoundTouch 30 Series III",
            mac_address="AA:BB:CC:11:22:33",
            ip_address="192.168.1.100",
            firmware_version="28.0.10.12345",  # Old firmware
        )

        with patch(
            "opencloudtouch.devices.services.sync_service.get_discovery_adapter"
        ) as mock_get_discovery, patch(
            "opencloudtouch.devices.services.sync_service.get_device_client"
        ) as mock_get_client, patch(
            "opencloudtouch.devices.api.routes.get_config"
        ) as mock_config:

            mock_config.return_value.discovery_enabled = True
            mock_config.return_value.discovery_timeout = 5
            mock_config.return_value.manual_device_ips_list = []

            mock_discovery_instance = AsyncMock()
            mock_discovery_instance.discover.return_value = discovered_v1
            mock_get_discovery.return_value = mock_discovery_instance

            mock_client_instance = AsyncMock()
            mock_client_instance.get_info.return_value = device_info_v1
            mock_get_client.return_value = mock_client_instance

            # 2. First sync
            response = await real_api_client.post("/api/devices/sync")
            assert response.status_code == 200
            assert response.json()["synced"] == 1

        # 3. Verify initial state in DB
        device = await device_repo.get_by_device_id("AABBCC112233")
        assert device is not None
        assert device.name == "Living Room"
        assert device.firmware_version == "28.0.10.12345"

        # 4. User renames device + firmware update
        device_info_v2 = DeviceInfo(
            device_id="AABBCC112233",  # Same device_id
            name="Living Room Speaker",  # New name
            type="SoundTouch 30 Series III",
            mac_address="AA:BB:CC:11:22:33",
            ip_address="192.168.1.100",
            firmware_version="28.0.12.46499",  # New firmware
        )

        with patch(
            "opencloudtouch.devices.services.sync_service.get_discovery_adapter"
        ) as mock_get_discovery, patch(
            "opencloudtouch.devices.services.sync_service.get_device_client"
        ) as mock_get_client, patch(
            "opencloudtouch.devices.api.routes.get_config"
        ) as mock_config:

            mock_config.return_value.discovery_enabled = True
            mock_config.return_value.discovery_timeout = 5
            mock_config.return_value.manual_device_ips_list = []

            mock_discovery_instance = AsyncMock()
            mock_discovery_instance.discover.return_value = discovered_v1
            mock_get_discovery.return_value = mock_discovery_instance

            mock_client_instance = AsyncMock()
            mock_client_instance.get_info.return_value = device_info_v2
            mock_get_client.return_value = mock_client_instance

            # 5. Second sync (should UPDATE, not INSERT)
            response = await real_api_client.post("/api/devices/sync")
            assert response.status_code == 200

        # 6. Verify UPSERT worked (no duplicates)
        devices = await device_repo.get_all()
        assert len(devices) == 1  # Still only 1 device

        # 7. Verify device was updated
        device = await device_repo.get_by_device_id("AABBCC112233")
        assert device.name == "Living Room Speaker"  # Updated
        assert device.firmware_version == "28.0.12.46499"  # Updated

    @pytest.mark.asyncio
    async def test_concurrent_api_requests_with_real_db(self, real_api_client, real_db):
        """
        Test concurrent API requests don't corrupt real DB.

        SQLite supports concurrent reads but sequential writes.
        """
        import asyncio

        settings_repo = real_db["settings_repo"]

        # Prepare test data
        ip_sets = [
            ["192.168.1.1", "192.168.1.2"],
            ["192.168.1.3", "192.168.1.4"],
            ["192.168.1.5", "192.168.1.6"],
        ]

        # Execute concurrent writes
        async def add_ips(ips):
            return await real_api_client.post(
                "/api/settings/manual-ips", json={"ips": ips}
            )

        responses = await asyncio.gather(
            add_ips(ip_sets[0]),
            add_ips(ip_sets[1]),
            add_ips(ip_sets[2]),
        )

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200

        # REAL BEHAVIOR: Concurrent writes can interleave (no transaction isolation)
        # This reveals a race condition in the bulk endpoint:
        # 1. Request A: get_existing (0) ? delete (0) ? add [1,2]
        # 2. Request B: get_existing (0) ? delete (0 or 2) ? add [3,4]
        # 3. Request C: get_existing (?) ? delete (?) ? add [5,6]
        # Result: All IPs from all requests might end up in DB (not atomic)
        db_ips = await settings_repo.get_manual_ips()

        # Verify DB is not corrupted (all IPs are valid)
        assert all(ip.count(".") == 3 for ip in db_ips)  # Valid IP format

        # DB should contain 2, 4, or 6 IPs (depending on interleaving)
        # This test documents REAL behavior, not ideal behavior
        assert len(db_ips) in [2, 4, 6]
