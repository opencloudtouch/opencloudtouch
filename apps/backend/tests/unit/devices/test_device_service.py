"""Unit tests for DeviceService.

Tests business logic layer for device operations.
Following TDD Red-Green-Refactor cycle.
"""

from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.core.exceptions import DeviceNotFoundError, DomainValidationError
from opencloudtouch.devices.client import NowPlayingInfo, VolumeInfo
from opencloudtouch.devices.models import KeyType, SyncResult
from opencloudtouch.devices.repository import Device
from opencloudtouch.devices.service import DeviceService
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
        from unittest.mock import AsyncMock

        # Arrange
        mock_repository.get_by_device_id.return_value = sample_device

        expected_capabilities = {
            "model": "SoundTouch 30 Series III",
            "api_version": "1.0",
            "has_hdmi": False,
        }

        expected_feature_flags = {
            "device_id": "AABBCC112233",
            "device_model": "SoundTouch 30 Series III",
            "is_soundbar": False,
            "features": {
                "hdmi_control": False,
                "bass_control": True,
                "bluetooth": True,
            },
        }

        # Mock the capability detection and device client creation
        with patch(
            "opencloudtouch.devices.service.get_capabilities_for_ip",
            new_callable=AsyncMock,
        ) as mock_get_caps, patch(
            "opencloudtouch.devices.service.get_feature_flags_for_ui"
        ) as mock_get_flags:

            mock_get_caps.return_value = expected_capabilities
            mock_get_flags.return_value = expected_feature_flags

            # Act
            result = await device_service.get_device_capabilities("AABBCC112233")

            # Assert
            assert result["device_id"] == "AABBCC112233"
            assert result["features"]["bass_control"] is True
            mock_repository.get_by_device_id.assert_called_once_with("AABBCC112233")
            mock_get_caps.assert_called_once_with("192.168.1.100")
            mock_get_flags.assert_called_once_with(expected_capabilities)

    @pytest.mark.asyncio
    async def test_get_device_capabilities_device_not_found(
        self, device_service, mock_repository
    ):
        """Test getting capabilities when device not found."""
        # Arrange
        mock_repository.get_by_device_id.return_value = None

        # Act & Assert
        with pytest.raises(DeviceNotFoundError):
            await device_service.get_device_capabilities("NONEXISTENT")


class TestDeviceServiceSendKey:
    """Test playback key handling."""

    @pytest.mark.asyncio
    async def test_send_key_success(
        self, device_service, mock_repository, sample_device
    ):
        """Send supported playback key and return now playing info."""

        mock_repository.get_by_device_id.return_value = sample_device

        now_playing = NowPlayingInfo(
            source="INTERNET_RADIO",
            state="PLAY_STATE",
            station_name="Radio Paradise",
            artist="Various",
            track="Test Track",
            album=None,
            artwork_url=None,
        )

        from unittest.mock import AsyncMock

        mock_client = AsyncMock()
        mock_client.get_now_playing.return_value = now_playing

        with patch(
            "opencloudtouch.devices.service.get_device_client",
            return_value=mock_client,
        ) as mock_factory:
            result = await device_service.send_key(
                sample_device.device_id, KeyType.PLAY, state="press"
            )

        mock_repository.get_by_device_id.assert_called_once_with(
            sample_device.device_id
        )
        mock_factory.assert_called_once()
        mock_client.press_key.assert_awaited_once_with(KeyType.PLAY.value, "press")
        mock_client.get_now_playing.assert_awaited_once()
        mock_client.close.assert_awaited_once()

        assert result == now_playing

    @pytest.mark.asyncio
    async def test_send_key_invalid_key_raises(
        self, device_service, mock_repository, sample_device
    ):
        """Unsupported key raises ValueError."""

        mock_repository.get_by_device_id.return_value = sample_device

        with pytest.raises(DomainValidationError):
            await device_service.send_key(sample_device.device_id, "INVALID")

    @pytest.mark.asyncio
    async def test_send_key_device_not_found(self, device_service, mock_repository):
        """Device missing raises ValueError."""

        mock_repository.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await device_service.send_key("NONEXISTENT", KeyType.PAUSE)


class TestDeviceServiceSyncWithEvents:
    """Tests for sync_devices_with_events method."""

    @pytest.mark.asyncio
    async def test_sync_with_events_success(self, device_service, mock_sync_service):
        """Test successful sync publishes STARTED and COMPLETED events."""
        from unittest.mock import AsyncMock

        from opencloudtouch.devices.events import DiscoveryEventType

        mock_event_bus = AsyncMock()
        sync_result = SyncResult(discovered=2, synced=2, failed=0)
        mock_sync_service.sync_with_events = AsyncMock(return_value=sync_result)

        result = await device_service.sync_devices_with_events(mock_event_bus)

        assert result.discovered == 2
        assert result.synced == 2
        assert result.failed == 0

        # Verify STARTED and COMPLETED events published
        calls = mock_event_bus.publish.call_args_list
        event_types = [c[0][0].type for c in calls]
        assert DiscoveryEventType.STARTED in event_types
        assert DiscoveryEventType.COMPLETED in event_types

    @pytest.mark.asyncio
    async def test_sync_with_events_timeout_returns_empty_result(
        self, device_service, mock_sync_service
    ):
        """Test timeout path publishes ERROR event and returns empty SyncResult."""
        import asyncio

        from opencloudtouch.devices.events import DiscoveryEventType

        mock_event_bus = AsyncMock()
        mock_sync_service.sync_with_events = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        result = await device_service.sync_devices_with_events(mock_event_bus)

        # Returns empty result, does not raise
        assert result.discovered == 0
        assert result.synced == 0
        assert result.failed == 0

        # Verify ERROR event published
        calls = mock_event_bus.publish.call_args_list
        event_types = [c[0][0].type for c in calls]
        assert DiscoveryEventType.ERROR in event_types

    @pytest.mark.asyncio
    async def test_sync_with_events_exception_publishes_error_and_reraises(
        self, device_service, mock_sync_service
    ):
        """Test generic exception publishes ERROR event and re-raises."""
        from opencloudtouch.devices.events import DiscoveryEventType

        mock_event_bus = AsyncMock()
        mock_sync_service.sync_with_events = AsyncMock(
            side_effect=RuntimeError("Network failure")
        )

        with pytest.raises(RuntimeError, match="Network failure"):
            await device_service.sync_devices_with_events(mock_event_bus)

        # Verify ERROR event published
        calls = mock_event_bus.publish.call_args_list
        event_types = [c[0][0].type for c in calls]
        assert DiscoveryEventType.ERROR in event_types


class TestDeviceServicePressKey:
    """Tests for press_key method."""

    @pytest.mark.asyncio
    async def test_press_key_success(
        self, device_service, mock_repository, sample_device
    ):
        """Test press_key calls press_key on the device client."""
        mock_repository.get_by_device_id.return_value = sample_device

        mock_client = AsyncMock()
        mock_client.press_key = AsyncMock()
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.devices.service.get_device_client",
            return_value=mock_client,
        ):
            await device_service.press_key("AABBCC112233", "PRESET_1", "both")

        mock_client.press_key.assert_awaited_once_with("PRESET_1", "both")
        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_press_key_device_not_found(self, device_service, mock_repository):
        """Test press_key raises ValueError when device not in DB."""
        mock_repository.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await device_service.press_key("NONEXISTENT", "PRESET_1", "both")


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


class TestDeviceServiceVolume:
    """Tests for volume control methods."""

    @pytest.mark.asyncio
    async def test_get_volume_success(
        self, device_service, mock_repository, sample_device
    ):
        """Test get_volume returns VolumeInfo from the device client."""
        mock_repository.get_by_device_id.return_value = sample_device
        volume_info = VolumeInfo(actual=42, target=42, muted=False)

        mock_client = AsyncMock()
        mock_client.get_volume = AsyncMock(return_value=volume_info)
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.devices.service.get_device_client",
            return_value=mock_client,
        ):
            result = await device_service.get_volume("AABBCC112233")

        assert result.actual == 42
        assert result.muted is False
        mock_client.get_volume.assert_awaited_once()
        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_volume_device_not_found(self, device_service, mock_repository):
        """Test get_volume raises ValueError for unknown device."""
        mock_repository.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await device_service.get_volume("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_set_volume_success(
        self, device_service, mock_repository, sample_device
    ):
        """Test set_volume calls client and returns updated state."""
        mock_repository.get_by_device_id.return_value = sample_device
        updated = VolumeInfo(actual=70, target=70, muted=False)

        mock_client = AsyncMock()
        mock_client.set_volume = AsyncMock()
        mock_client.get_volume = AsyncMock(return_value=updated)
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.devices.service.get_device_client",
            return_value=mock_client,
        ):
            result = await device_service.set_volume("AABBCC112233", 70)

        assert result.actual == 70
        mock_client.set_volume.assert_awaited_once_with(70)
        mock_client.get_volume.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_volume_out_of_range(self, device_service):
        """Test set_volume raises ValueError for invalid level."""
        with pytest.raises(DomainValidationError):
            await device_service.set_volume("AABBCC112233", 150)

        with pytest.raises(DomainValidationError):
            await device_service.set_volume("AABBCC112233", -1)

    @pytest.mark.asyncio
    async def test_set_mute_success(
        self, device_service, mock_repository, sample_device
    ):
        """Test set_mute calls client and returns updated state."""
        mock_repository.get_by_device_id.return_value = sample_device
        updated = VolumeInfo(actual=42, target=42, muted=True)

        mock_client = AsyncMock()
        mock_client.set_mute = AsyncMock()
        mock_client.get_volume = AsyncMock(return_value=updated)
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.devices.service.get_device_client",
            return_value=mock_client,
        ):
            result = await device_service.set_mute("AABBCC112233", True)

        assert result.muted is True
        mock_client.set_mute.assert_awaited_once_with(True)

    @pytest.mark.asyncio
    async def test_set_mute_device_not_found(self, device_service, mock_repository):
        """Test set_mute raises ValueError for unknown device."""
        mock_repository.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await device_service.set_mute("NONEXISTENT", True)


class TestDeviceServiceNowPlaying:
    """Tests for now playing method."""

    @pytest.mark.asyncio
    async def test_get_now_playing_success(
        self, device_service, mock_repository, sample_device
    ):
        """Test get_now_playing returns NowPlayingInfo from device."""
        mock_repository.get_by_device_id.return_value = sample_device
        now_playing = NowPlayingInfo(
            source="INTERNET_RADIO",
            state="PLAY_STATE",
            station_name="Jazz FM",
            artist="Miles Davis",
            track="So What",
        )

        mock_client = AsyncMock()
        mock_client.get_now_playing = AsyncMock(return_value=now_playing)
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.devices.service.get_device_client",
            return_value=mock_client,
        ):
            result = await device_service.get_now_playing("AABBCC112233")

        assert result.source == "INTERNET_RADIO"
        assert result.station_name == "Jazz FM"
        assert result.artist == "Miles Davis"
        mock_client.get_now_playing.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_now_playing_device_not_found(
        self, device_service, mock_repository
    ):
        """Test get_now_playing raises ValueError for unknown device."""
        mock_repository.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await device_service.get_now_playing("NONEXISTENT")
