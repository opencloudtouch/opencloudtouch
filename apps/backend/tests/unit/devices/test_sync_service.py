"""Tests for DeviceSyncService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.db import Device
from opencloudtouch.devices.models import SyncResult
from opencloudtouch.devices.services.sync_service import DeviceSyncService
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

    # ── sync_with_events ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_sync_with_events_publishes_device_found(
        self, mock_repository, discovered_devices, mock_device_info, monkeypatch
    ):
        """sync_with_events() publishes device_found events for each discovery."""
        from unittest.mock import AsyncMock as _AM

        async def mock_discover_ssdp(self):
            return discovered_devices

        mock_client = _AM()
        mock_client.get_info = _AM(return_value=mock_device_info)
        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_discover_ssdp)
        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            lambda url: mock_client,
        )

        mock_bus = _AM()
        mock_bus.publish = _AM()

        service = DeviceSyncService(repository=mock_repository)
        result = await service.sync_with_events(mock_bus)

        assert result.discovered == 2
        assert result.synced == 2
        assert result.failed == 0
        # device_found (×2) + device_synced (×2) = 4 publish calls
        assert mock_bus.publish.call_count == 4

    @pytest.mark.asyncio
    async def test_sync_with_events_publishes_device_failed(
        self, mock_repository, discovered_devices, monkeypatch
    ):
        """sync_with_events() publishes device_failed for devices that error."""
        from unittest.mock import AsyncMock as _AM

        async def mock_discover_ssdp(self):
            return discovered_devices

        mock_client = _AM()
        mock_client.get_info = _AM(side_effect=Exception("timeout"))
        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_discover_ssdp)
        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            lambda url: mock_client,
        )

        mock_bus = _AM()
        mock_bus.publish = _AM()

        service = DeviceSyncService(repository=mock_repository)
        result = await service.sync_with_events(mock_bus)

        assert result.failed == 2
        assert result.synced == 0
        # device_found (×2) + device_failed (×2) = 4
        assert mock_bus.publish.call_count == 4

    @pytest.mark.asyncio
    async def test_sync_with_events_no_devices(self, mock_repository, monkeypatch):
        """sync_with_events() handles empty discovery list."""
        from unittest.mock import AsyncMock as _AM

        async def mock_discover_ssdp(self):
            return []

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_discover_ssdp)

        mock_bus = _AM()
        mock_bus.publish = _AM()

        service = DeviceSyncService(repository=mock_repository)
        result = await service.sync_with_events(mock_bus)

        assert result.discovered == 0
        assert result.synced == 0
        assert mock_bus.publish.call_count == 0

    # ── error paths in _discover_via_ssdp / _discover_via_manual_ips ───────

    @pytest.mark.asyncio
    async def test_discover_via_ssdp_returns_empty_on_exception(
        self, mock_repository, monkeypatch
    ):
        """_discover_via_ssdp() returns [] when discovery raises."""
        from unittest.mock import AsyncMock as _AM

        async def failing_discover(*args, **kwargs):
            raise RuntimeError("network error")

        mock_adapter = _AM()
        mock_adapter.discover = _AM(side_effect=RuntimeError("network error"))

        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_discovery_adapter",
            lambda timeout: mock_adapter,
        )

        service = DeviceSyncService(repository=mock_repository, discovery_enabled=True)
        result = await service._discover_via_ssdp()
        assert result == []

    @pytest.mark.asyncio
    async def test_discover_via_manual_ips_returns_empty_on_exception(
        self, mock_repository, monkeypatch
    ):
        """_discover_via_manual_ips() returns [] when discovery raises."""

        class FailingManual:
            def __init__(self, ips):
                pass

            async def discover(self):
                raise RuntimeError("cannot reach")

        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.ManualDiscovery",
            FailingManual,
        )

        service = DeviceSyncService(
            repository=mock_repository, manual_ips=["192.168.1.50"]
        )
        result = await service._discover_via_manual_ips()
        assert result == []


class TestDeviceSyncServiceDeduplication:
    """Regression tests for device deduplication in _discover_devices.

    Bug: When a device appears in both SSDP and manual-IP results, it would be
    synced twice — producing an incorrect SyncResult.discovered count and
    redundant API calls to the device.

    Fixed: _discover_devices() deduplicates by IP address before returning.
    """

    @pytest.mark.asyncio
    async def test_duplicate_ip_removed(self, mock_repository, monkeypatch):
        """Devices found by both SSDP and manual IPs are deduplicated by IP."""
        shared_ip = DiscoveredDevice(
            ip="192.168.1.100", port=8090, model="SoundTouch 30"
        )
        ssdp_only = DiscoveredDevice(
            ip="192.168.1.101", port=8090, model="SoundTouch 10"
        )

        async def mock_ssdp(self):
            return [shared_ip, ssdp_only]

        async def mock_manual(self):
            # Same IP as shared_ip — should be deduplicated
            return [
                DiscoveredDevice(ip="192.168.1.100", port=8090, model="SoundTouch 30")
            ]

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_ssdp)
        monkeypatch.setattr(DeviceSyncService, "_discover_via_manual_ips", mock_manual)

        service = DeviceSyncService(
            repository=mock_repository,
            manual_ips=["192.168.1.100"],
            discovery_enabled=True,
        )
        result = await service._discover_devices()

        assert len(result) == 2
        ips = [d.ip for d in result]
        assert "192.168.1.100" in ips
        assert "192.168.1.101" in ips

    @pytest.mark.asyncio
    async def test_no_duplicates_unchanged(self, mock_repository, monkeypatch):
        """When no duplicates exist, all devices are returned."""
        dev_a = DiscoveredDevice(ip="192.168.1.10", port=8090, model="SoundTouch 30")
        dev_b = DiscoveredDevice(ip="192.168.1.20", port=8090, model="SoundTouch 10")
        dev_c = DiscoveredDevice(ip="192.168.1.30", port=8090, model="SoundTouch 10")

        async def mock_ssdp(self):
            return [dev_a, dev_b]

        async def mock_manual(self):
            return [dev_c]

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_ssdp)
        monkeypatch.setattr(DeviceSyncService, "_discover_via_manual_ips", mock_manual)

        service = DeviceSyncService(
            repository=mock_repository,
            manual_ips=["192.168.1.30"],
            discovery_enabled=True,
        )
        result = await service._discover_devices()

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_sync_result_counts_unique_devices(
        self, mock_repository, monkeypatch
    ):
        """SyncResult.discovered reflects unique devices, not raw count."""
        shared_ip = DiscoveredDevice(
            ip="192.168.1.100", port=8090, model="SoundTouch 30"
        )

        async def mock_ssdp(self):
            return [shared_ip]

        async def mock_manual(self):
            # Same IP — after deduplication only 1 total device
            return [
                DiscoveredDevice(ip="192.168.1.100", port=8090, model="SoundTouch 30")
            ]

        mock_info = MagicMock()
        mock_info.device_id = "AABBCCDDEE00"
        mock_info.name = "Kitchen"
        mock_info.type = "SoundTouch 30"
        mock_info.mac_address = "AA:BB:CC:DD:EE:00"
        mock_info.firmware_version = "28.0.0"

        async def mock_fetch(self, discovered):
            return Device(
                device_id=mock_info.device_id,
                ip=discovered.ip,
                name=mock_info.name,
                model=mock_info.type,
                mac_address=mock_info.mac_address,
                firmware_version=mock_info.firmware_version,
            )

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_ssdp)
        monkeypatch.setattr(DeviceSyncService, "_discover_via_manual_ips", mock_manual)
        monkeypatch.setattr(DeviceSyncService, "_fetch_device_info", mock_fetch)

        service = DeviceSyncService(
            repository=mock_repository,
            manual_ips=["192.168.1.100"],
            discovery_enabled=True,
        )
        result = await service.sync()

        # discovered must reflect unique count (1), not raw count (2)
        assert result.discovered == 1
        assert result.synced == 1
        assert result.failed == 0


class TestFetchAndUpsertOne:
    """Tests for fetch_and_upsert_one."""

    @pytest.mark.asyncio
    async def test_fetch_and_upsert_one_success(self, mock_repository, monkeypatch):
        """Fetches device info and upserts to DB."""
        discovered = DiscoveredDevice(ip="192.168.1.50", port=8090)

        fetched_device = Device(
            device_id="AABB11223344",
            ip="192.168.1.50",
            name="Kitchen",
            model="SoundTouch 20",
            mac_address="AA:BB:11:22:33:44",
            firmware_version="28.0.3.46454",
        )

        async def mock_fetch(self, disc):
            return fetched_device

        monkeypatch.setattr(DeviceSyncService, "_fetch_device_info", mock_fetch)

        service = DeviceSyncService(repository=mock_repository)
        result = await service.fetch_and_upsert_one(discovered)

        assert result.device_id == "AABB11223344"
        assert result.name == "Kitchen"
        mock_repository.upsert.assert_called_once_with(fetched_device)

    @pytest.mark.asyncio
    async def test_fetch_and_upsert_one_propagates_error(
        self, mock_repository, monkeypatch
    ):
        """Propagates exceptions from _fetch_device_info."""
        discovered = DiscoveredDevice(ip="192.168.1.99", port=8090)

        async def mock_fetch(self, disc):
            raise Exception("Device offline")

        monkeypatch.setattr(DeviceSyncService, "_fetch_device_info", mock_fetch)

        service = DeviceSyncService(repository=mock_repository)

        with pytest.raises(Exception, match="Device offline"):
            await service.fetch_and_upsert_one(discovered)
