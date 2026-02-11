"""Unit tests for DeviceService.

Tests business logic layer for device operations.
Following TDD Red-Green-Refactor cycle.
"""

import pytest
from unittest.mock import AsyncMock, patch

from opencloudtouch.devices.repository import Device
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.services.sync_service import SyncResult
from opencloudtouch.discovery import DiscoveredDevice


@pytest.fixture
def mock_repository():
    """Mock DeviceRepository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_sync_service():
    """Mock DeviceSyncService."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_adapter():
    """Mock BoseDeviceDiscoveryAdapter."""
    adapter = AsyncMock()
    return adapter


@pytest.fixture
def device_service(mock_repository, mock_sync_service, mock_adapter):
    """DeviceService instance with mocked dependencies."""
    return DeviceService(
        repository=mock_repository,
        sync_service=mock_sync_service,
        discovery_adapter=mock_adapter,
    )


@pytest.fixture
def sample_discovered_device():
    """Sample discovered device."""
    return DiscoveredDevice(
        ip="192.168.1.100",
        port=8090,
        name="Living Room",
        model="SoundTouch 30",
    )


@pytest.fixture
def sample_device():
    """Sample persisted device."""
    return Device(
        device_id="AABBCC112233",
        ip="192.168.1.100",
        name="Living Room",
        model="SoundTouch 30 Series III",
        mac_address="AA:BB:CC:11:22:33",
        firmware_version="28.0.3.46454",
    )


class TestDeviceServiceDiscovery:
    """Test device discovery orchestration."""

    @pytest.mark.asyncio
    async def test_discover_devices_success(
        self, device_service, mock_adapter, sample_discovered_device
    ):
        """Test successful device discovery."""
        # Arrange
        mock_adapter.discover.return_value = [sample_discovered_device]

        # Act
        result = await device_service.discover_devices(timeout=10)

        # Assert
        assert len(result) == 1
        assert result[0].ip == "192.168.1.100"
        assert result[0].name == "Living Room"
        mock_adapter.discover.assert_called_once_with(timeout=10)

    @pytest.mark.asyncio
    async def test_discover_devices_empty(self, device_service, mock_adapter):
        """Test discovery when no devices found."""
        # Arrange
        mock_adapter.discover.return_value = []

        # Act
        result = await device_service.discover_devices(timeout=10)

        # Assert
        assert result == []
        mock_adapter.discover.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_devices_handles_adapter_error(
        self, device_service, mock_adapter
    ):
        """Test discovery when adapter fails."""
        # Arrange
        mock_adapter.discover.side_effect = Exception("Network error")

        # Act & Assert
        with pytest.raises(Exception, match="Network error"):
            await device_service.discover_devices(timeout=10)


class TestDeviceServiceSync:
    """Test device sync orchestration."""

    @pytest.mark.asyncio
    async def test_sync_devices_success(self, device_service, mock_sync_service):
        """Test successful device sync."""
        # Arrange
        sync_result = SyncResult(discovered=2, synced=2, failed=0)
        mock_sync_service.sync.return_value = sync_result

        # Act
        result = await device_service.sync_devices()

        # Assert
        assert result.discovered == 2
        assert result.synced == 2
        assert result.failed == 0
        mock_sync_service.sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_devices_partial_failure(
        self, device_service, mock_sync_service
    ):
        """Test sync with some devices failing."""
        # Arrange
        sync_result = SyncResult(discovered=3, synced=2, failed=1)
        mock_sync_service.sync.return_value = sync_result

        # Act
        result = await device_service.sync_devices()

        # Assert
        assert result.discovered == 3
        assert result.synced == 2
        assert result.failed == 1


class TestDeviceServiceRetrieval:
    """Test device retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_all_devices_success(
        self, device_service, mock_repository, sample_device
    ):
        """Test getting all devices."""
        # Arrange
        mock_repository.get_all.return_value = [sample_device]

        # Act
        result = await device_service.get_all_devices()

        # Assert
        assert len(result) == 1
        assert result[0].device_id == "AABBCC112233"
        assert result[0].name == "Living Room"
        mock_repository.get_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_devices_empty(self, device_service, mock_repository):
        """Test getting all devices when none exist."""
        # Arrange
        mock_repository.get_all.return_value = []

        # Act
        result = await device_service.get_all_devices()

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_device_by_id_success(
        self, device_service, mock_repository, sample_device
    ):
        """Test getting device by ID."""
        # Arrange
        mock_repository.get_by_device_id.return_value = sample_device

        # Act
        result = await device_service.get_device_by_id("AABBCC112233")

        # Assert
        assert result is not None
        assert result.device_id == "AABBCC112233"
        assert result.name == "Living Room"
        mock_repository.get_by_device_id.assert_called_once_with("AABBCC112233")

    @pytest.mark.asyncio
    async def test_get_device_by_id_not_found(self, device_service, mock_repository):
        """Test getting device by ID when not found."""
        # Arrange
        mock_repository.get_by_device_id.return_value = None

        # Act
        result = await device_service.get_device_by_id("NONEXISTENT")

        # Assert
        assert result is None
        mock_repository.get_by_device_id.assert_called_once_with("NONEXISTENT")


class TestDeviceServiceCapabilities:
    """Test device capability queries."""

    @pytest.mark.asyncio
    async def test_get_device_capabilities_success(
        self, device_service, mock_repository, sample_device
    ):
        """Test getting device capabilities."""
        # Arrange
        mock_repository.get_by_device_id.return_value = sample_device
        expected_capabilities = {
            "device_id": "AABBCC112233",
            "device_model": "SoundTouch 30 Series III",
            "is_soundbar": False,
            "features": {
                "hdmi_control": False,
                "bass_control": True,
                "bluetooth": True,
            },
        }

        # Mock the capability detection
        with patch("opencloudtouch.devices.service.get_device_capabilities"), patch(
            "opencloudtouch.devices.service.get_feature_flags_for_ui"
        ) as mock_get_flags:
            mock_get_flags.return_value = expected_capabilities

            # Act
            result = await device_service.get_device_capabilities("AABBCC112233")

            # Assert
            assert result["device_id"] == "AABBCC112233"
            assert result["features"]["bass_control"] is True
            mock_repository.get_by_device_id.assert_called_once_with("AABBCC112233")

    @pytest.mark.asyncio
    async def test_get_device_capabilities_device_not_found(
        self, device_service, mock_repository
    ):
        """Test getting capabilities when device not found."""
        # Arrange
        mock_repository.get_by_device_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Device not found"):
            await device_service.get_device_capabilities("NONEXISTENT")


class TestDeviceServiceDeletion:
    """Test device deletion operations."""

    @pytest.mark.asyncio
    async def test_delete_all_devices_when_allowed(
        self, device_service, mock_repository
    ):
        """Test deleting all devices when dangerous operations allowed."""
        # Arrange
        mock_repository.delete_all.return_value = None

        # Act
        await device_service.delete_all_devices(allow_dangerous_operations=True)

        # Assert
        mock_repository.delete_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_all_devices_when_not_allowed(
        self, device_service, mock_repository
    ):
        """Test deleting all devices when dangerous operations disabled."""
        # Act & Assert
        with pytest.raises(PermissionError, match="Dangerous operations are disabled"):
            await device_service.delete_all_devices(allow_dangerous_operations=False)

        # Assert repository was never called
        mock_repository.delete_all.assert_not_called()
