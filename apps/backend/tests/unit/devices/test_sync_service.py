"""Tests for DeviceSyncService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.db import Device
from opencloudtouch.devices.services.sync_service import DeviceSyncService
from opencloudtouch.devices.models import SyncResult
from opencloudtouch.discovery import DiscoveredDevice


@pytest.fixture
def mock_repository():
    """Create mock device repository."""
    repo = AsyncMock()
    repo.upsert = AsyncMock()
    return repo


@pytest.fixture
def discovered_devices():
    """Sample discovered devices."""
    return [
        DiscoveredDevice(ip="192.168.1.10", port=8090, model="SoundTouch 30"),
        DiscoveredDevice(ip="192.168.1.20", port=8090, model="SoundTouch 10"),
    ]


@pytest.fixture
def mock_device_info():
    """Sample device info from client."""
    info = MagicMock()
    info.device_id = "AABBCCDDEEFF"
    info.name = "Living Room"
    info.type = "SoundTouch 30"
    info.mac_address = "AA:BB:CC:DD:EE:FF"
    info.firmware_version = "28.0.6.46539"
    return info


class TestDeviceSyncService:
    """Test suite for DeviceSyncService."""

    def test_service_initialization(self, mock_repository):
        """Test service can be instantiated with required dependencies."""
        service = DeviceSyncService(
            repository=mock_repository,
            discovery_timeout=10,
            manual_ips=["192.168.1.30"],
            discovery_enabled=True,
        )

        assert service.repository is mock_repository
        assert service.discovery_timeout == 10
        assert service.manual_ips == ["192.168.1.30"]
        assert service.discovery_enabled is True

    def test_service_defaults(self, mock_repository):
        """Test service uses defaults when optional params omitted."""
        service = DeviceSyncService(repository=mock_repository)

        assert service.discovery_timeout == 10
        assert service.manual_ips == []
        assert service.discovery_enabled is True

    @pytest.mark.asyncio
    async def test_sync_no_devices_discovered(self, mock_repository, monkeypatch):
        """Test sync when no devices are discovered."""

        # Mock discovery to return empty list
        async def mock_discover_ssdp(self):
            return []

        async def mock_discover_manual(self):
            return []

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_discover_ssdp)
        monkeypatch.setattr(
            DeviceSyncService, "_discover_via_manual_ips", mock_discover_manual
        )

        service = DeviceSyncService(repository=mock_repository)
        result = await service.sync()

        assert isinstance(result, SyncResult)
        assert result.discovered == 0
        assert result.synced == 0
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_sync_success(
        self, mock_repository, discovered_devices, mock_device_info, monkeypatch
    ):
        """Test successful device synchronization."""

        # Mock discovery
        async def mock_discover_ssdp(self):
            return discovered_devices

        # Mock device client
        mock_client = AsyncMock()
        mock_client.get_info = AsyncMock(return_value=mock_device_info)

        def mock_get_client(base_url):
            return mock_client

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_discover_ssdp)
        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            mock_get_client,
        )

        service = DeviceSyncService(
            repository=mock_repository, manual_ips=[], discovery_enabled=True
        )
        result = await service.sync()

        assert result.discovered == 2
        assert result.synced == 2
        assert result.failed == 0
        assert mock_repository.upsert.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_with_failures(
        self, mock_repository, discovered_devices, monkeypatch
    ):
        """Test sync handles device query failures gracefully."""

        # Mock discovery
        async def mock_discover_ssdp(self):
            return discovered_devices

        # Mock client - first succeeds, second fails
        call_count = 0

        def mock_get_client(base_url):
            nonlocal call_count
            call_count += 1

            mock_client = AsyncMock()
            if call_count == 1:
                info = MagicMock()
                info.device_id = "AABBCCDDEEFF"
                info.name = "Living Room"
                info.type = "SoundTouch 30"
                info.mac_address = "AA:BB:CC:DD:EE:FF"
                info.firmware_version = "28.0.6"
                mock_client.get_info = AsyncMock(return_value=info)
            else:
                mock_client.get_info = AsyncMock(
                    side_effect=Exception("Connection timeout")
                )

            return mock_client

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_discover_ssdp)
        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            mock_get_client,
        )

        service = DeviceSyncService(repository=mock_repository)
        result = await service.sync()

        assert result.discovered == 2
        assert result.synced == 1
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_sync_combines_ssdp_and_manual(self, mock_repository, monkeypatch):
        """Test sync combines SSDP and manual discovery."""
        ssdp_device = DiscoveredDevice(
            ip="192.168.1.10", port=8090, model="SoundTouch 30"
        )
        manual_device = DiscoveredDevice(
            ip="192.168.1.20", port=8090, model="SoundTouch 10"
        )

        async def mock_discover_ssdp(self):
            return [ssdp_device]

        async def mock_discover_manual(self):
            return [manual_device]

        mock_client = AsyncMock()
        mock_info = MagicMock()
        mock_info.device_id = "TEST123"
        mock_info.name = "Test Device"
        mock_info.type = "SoundTouch 30"
        mock_info.mac_address = "AA:BB:CC:DD:EE:FF"
        mock_info.firmware_version = "28.0.6"
        mock_client.get_info = AsyncMock(return_value=mock_info)

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_discover_ssdp)
        monkeypatch.setattr(
            DeviceSyncService, "_discover_via_manual_ips", mock_discover_manual
        )
        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            lambda url: mock_client,
        )

        service = DeviceSyncService(
            repository=mock_repository, manual_ips=["192.168.1.20"]
        )
        result = await service.sync()

        assert result.discovered == 2  # Both sources
        assert result.synced == 2
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_sync_ssdp_disabled(self, mock_repository, monkeypatch):
        """Test sync works with SSDP disabled."""
        manual_device = DiscoveredDevice(
            ip="192.168.1.20", port=8090, model="SoundTouch 10"
        )

        async def mock_discover_manual(self):
            return [manual_device]

        mock_client = AsyncMock()
        mock_info = MagicMock()
        mock_info.device_id = "TEST123"
        mock_info.name = "Test Device"
        mock_info.type = "SoundTouch 10"
        mock_info.mac_address = "AA:BB:CC:DD:EE:FF"
        mock_info.firmware_version = "28.0.6"
        mock_client.get_info = AsyncMock(return_value=mock_info)

        monkeypatch.setattr(
            DeviceSyncService, "_discover_via_manual_ips", mock_discover_manual
        )
        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            lambda url: mock_client,
        )

        service = DeviceSyncService(
            repository=mock_repository,
            manual_ips=["192.168.1.20"],
            discovery_enabled=False,  # SSDP disabled
        )
        result = await service.sync()

        assert result.discovered == 1  # Only manual
        assert result.synced == 1

    @pytest.mark.asyncio
    async def test_fetch_device_info_creates_device(
        self, mock_repository, mock_device_info, monkeypatch
    ):
        """Test _fetch_device_info creates Device from discovered device."""
        discovered = DiscoveredDevice(
            ip="192.168.1.10", port=8090, model="SoundTouch 30"
        )

        mock_client = AsyncMock()
        mock_client.get_info = AsyncMock(return_value=mock_device_info)

        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            lambda url: mock_client,
        )

        service = DeviceSyncService(repository=mock_repository)
        device = await service._fetch_device_info(discovered)

        assert isinstance(device, Device)
        assert device.device_id == "AABBCCDDEEFF"
        assert device.ip == "192.168.1.10"
        assert device.name == "Living Room"
        assert device.model == "SoundTouch 30"

    def test_sync_result_to_dict(self):
        """Test SyncResult converts to dict for API response."""
        result = SyncResult(discovered=5, synced=3, failed=2)
        result_dict = result.to_dict()

        assert result_dict == {
            "discovered": 5,
            "synced": 3,
            "failed": 2,
        }
