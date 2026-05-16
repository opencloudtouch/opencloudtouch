"""Device service - Business logic layer for device operations.

Orchestrates device discovery, synchronization, and management.
Separates HTTP layer (routes) from business logic from data layer (repository).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional, Union

from opencloudtouch.core.exceptions import DeviceNotFoundError, DomainValidationError
from opencloudtouch.db import Device
from opencloudtouch.devices.adapter import get_device_client
from opencloudtouch.devices.capabilities import (
    get_capabilities_for_ip,
    get_feature_flags_for_ui,
)
from opencloudtouch.devices.client import NowPlayingInfo, VolumeInfo
from opencloudtouch.devices.interfaces import (
    IDeviceRepository,
    IDeviceSyncService,
    IDiscoveryAdapter,
)
from opencloudtouch.devices.events import DiscoveryEvent, DiscoveryEventType
from opencloudtouch.devices.models import KEY_MAPPING, KeyType, SyncResult
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT, DiscoveredDevice

logger = logging.getLogger(__name__)


class DeviceService:
    """Service for managing device operations.

    This service provides business logic for device operations,
    ensuring separation between HTTP layer (routes) and data layer (repository).

    Responsibilities:
    - Orchestrate device discovery
    - Orchestrate device synchronization (via IDeviceSyncService)
    - Manage device data access (via IDeviceRepository)
    - Handle device capability queries
    """

    # REFACT-014: Named constant replaces inline magic number (5s SSDP + DB sync margin)
    _SYNC_STREAM_TIMEOUT: int = 15

    def __init__(
        self,
        repository: IDeviceRepository,
        sync_service: IDeviceSyncService,
        discovery_adapter: IDiscoveryAdapter,
    ):
        """Initialize device service.

        Args:
            repository: IDeviceRepository for data persistence
            sync_service: IDeviceSyncService for sync operations
            discovery_adapter: IDiscoveryAdapter for discovery
        """
        self.repository = repository
        self.sync_service = sync_service
        self.discovery_adapter = discovery_adapter

    async def discover_devices(self, timeout: int = 10) -> List[DiscoveredDevice]:
        """Discover devices on the network.

        Uses SSDP/UPnP discovery to find Bose SoundTouch devices.

        Args:
            timeout: Discovery timeout in seconds

        Returns:
            List of discovered devices

        Raises:
            Exception: If discovery fails
        """
        logger.info("Starting device discovery (timeout: %ss)", timeout)

        devices = await self.discovery_adapter.discover(timeout=timeout)

        logger.info("Discovery complete: %d device(s) found", len(devices))
        for d in devices:
            logger.debug("Discovered: ip=%s, name=%s", d.ip, getattr(d, "name", "?"))

        return devices

    async def sync_devices(self) -> SyncResult:
        """Synchronize devices to database.

        Discovers devices and queries each for detailed info, then persists to DB.

        Returns:
            SyncResult with discovery/sync statistics
        """
        logger.info("Starting device sync")

        result = await self.sync_service.sync()

        logger.info(
            f"Sync complete: {result.synced} synced, {result.failed} failed "
            f"(discovered: {result.discovered})"
        )

        return result

    async def sync_devices_with_events(self, event_bus) -> SyncResult:
        """Synchronize devices to database with event streaming.

        Same as sync_devices() but publishes events to event_bus for SSE streaming.

        Args:
            event_bus: DiscoveryEventBus for publishing events

        Returns:
            SyncResult with discovery/sync statistics
        """
        logger.info("Starting device sync with event streaming")

        # Publish started event
        await event_bus.publish(
            DiscoveryEvent(
                type=DiscoveryEventType.STARTED,
                data={"message": "Starting device discovery"},
            )
        )

        try:
            # Run sync with event callbacks
            # asyncio.timeout as backstop: SSDP runs in thread executor so
            # cancellation is handled at coroutine level
            async with asyncio.timeout(self._SYNC_STREAM_TIMEOUT):
                result = await self.sync_service.sync_with_events(event_bus)

            # Publish completed event
            await event_bus.publish(
                DiscoveryEvent(
                    type=DiscoveryEventType.COMPLETED,
                    data={
                        "discovered": result.discovered,
                        "synced": result.synced,
                        "failed": result.failed,
                    },
                )
            )

            logger.info(
                f"Sync complete: {result.synced} synced, {result.failed} failed "
                f"(discovered: {result.discovered})"
            )

            return result

        except asyncio.TimeoutError:
            error_msg = (
                f"Discovery timed out after {self._SYNC_STREAM_TIMEOUT}s (SSDP hanging)"
            )
            logger.error(error_msg)
            # Publish timeout error event
            await event_bus.publish(
                DiscoveryEvent(
                    type=DiscoveryEventType.ERROR,
                    data={"message": error_msg},
                )
            )
            # Return empty result instead of crashing
            return SyncResult(discovered=0, synced=0, failed=0)

        except Exception as e:
            logger.exception("Sync with events failed")
            # Publish error event
            await event_bus.publish(
                DiscoveryEvent(type=DiscoveryEventType.ERROR, data={"message": str(e)})
            )
            raise

    async def get_all_devices(self) -> List[Device]:
        """Get all devices from database.

        Returns:
            List of all devices
        """
        return await self.repository.get_all()

    async def get_device_by_id(self, device_id: str) -> Optional[Device]:
        """Get device by ID.

        Args:
            device_id: Device ID

        Returns:
            Device if found, None otherwise
        """
        return await self.repository.get_by_device_id(device_id)

    async def get_device_capabilities(self, device_id: str) -> dict:
        """Get device capabilities for UI feature detection.

        Args:
            device_id: Device ID

        Returns:
            Feature flags and capabilities for UI rendering

        Raises:
            ValueError: If device not found
            Exception: If device query fails
        """
        # Get device from DB
        device = await self.repository.get_by_device_id(device_id)

        if not device:
            raise DeviceNotFoundError(device_id)

        logger.info("Querying device capabilities")

        try:
            capabilities = await get_capabilities_for_ip(device.ip)
            flags = get_feature_flags_for_ui(capabilities)
            logger.debug("Device capabilities resolved")
            return flags

        except Exception:
            logger.exception("Failed to get device capabilities")
            raise

    @asynccontextmanager
    async def _device_client(self, device_id: str) -> AsyncIterator:
        """Async context manager: look up device, create HTTP client, ensure close.

        Args:
            device_id: Device ID to look up

        Yields:
            Configured device HTTP client

        Raises:
            ValueError: If device not found in repository
        """
        device = await self.repository.get_by_device_id(device_id)
        if not device:
            raise DeviceNotFoundError(device_id)
        base_url = f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR — Bose devices only support HTTP
        client = await asyncio.to_thread(get_device_client, base_url)
        try:
            yield client
        finally:
            await client.close()

    async def press_key(self, device_id: str, key: str, state: str = "both") -> None:
        """
        Simulate a key press on a device.

        Args:
            device_id: Device ID
            key: Key name (e.g., "PRESET_1", "PRESET_2", ...)
            state: Key state ("press", "release", or "both")

        Raises:
            ValueError: If device not found
            Exception: If key press fails
        """
        logger.info(  # NOSONAR
            "Pressing key %s on device %s (state: %s)", key, device_id, state
        )
        async with self._device_client(device_id) as client:
            await client.press_key(key, state)
        logger.info(  # NOSONAR
            "Successfully pressed key %s on device %s", key, device_id
        )

    async def delete_all_devices(self, allow_dangerous_operations: bool) -> None:
        """Delete all devices from database.

        **Testing/Development only.**

        Args:
            allow_dangerous_operations: Must be True to proceed

        Raises:
            PermissionError: If dangerous operations are disabled
        """
        if not allow_dangerous_operations:
            raise PermissionError(
                "Dangerous operations are disabled. "
                "Set OCT_ALLOW_DANGEROUS_OPERATIONS=true to enable (testing only)"
            )

        logger.warning("Deleting all devices from database")

        await self.repository.delete_all()

        logger.info("All devices deleted")

    async def delete_by_device_id(self, device_id: str) -> None:
        """Delete device by id from database.

        Args:
            device_id: Id of the device to delete
        """

        await self.repository.delete_by_device_id(device_id)

        logger.info("Successfully deleted device with id %s", device_id)

    async def send_key(
        self, device_id: str, key: Union[KeyType, str], state: str = "both"
    ) -> NowPlayingInfo:
        """Send playback key and return now playing info.

        Args:
            device_id: Target device ID
            key: Supported key (KeyType or string value)
            state: press|release|both

        Raises:
            ValueError: If device missing, key invalid, or state invalid
        """

        try:
            key_enum = key if isinstance(key, KeyType) else KeyType(key)
        except Exception:
            raise DomainValidationError(
                f"Unsupported key: {key}", field="key"
            ) from None

        valid_states = {"press", "release", "both"}
        if state not in valid_states:
            raise DomainValidationError(
                f"Invalid state: {state}. Must be one of {sorted(valid_states)}",
                field="state",
            )

        mapped = KEY_MAPPING.get(key_enum)
        if mapped is None:
            raise DomainValidationError(f"Unsupported key: {key}", field="key")

        key_value = mapped.value if hasattr(mapped, "value") else str(mapped)

        async with self._device_client(device_id) as client:
            await client.press_key(key_value, state)
            now_playing = await client.get_now_playing()
        return now_playing

    async def get_now_playing(self, device_id: str) -> NowPlayingInfo:
        """Get now playing info for a device."""
        async with self._device_client(device_id) as client:
            return await client.get_now_playing()

    async def get_volume(self, device_id: str) -> VolumeInfo:
        """Get current volume state for a device."""
        async with self._device_client(device_id) as client:
            return await client.get_volume()

    async def set_volume(self, device_id: str, level: int) -> VolumeInfo:
        """Set volume level and return updated state."""
        if not 0 <= level <= 100:
            raise DomainValidationError(
                f"Volume must be 0-100, got {level}", field="level"
            )
        async with self._device_client(device_id) as client:
            await client.set_volume(level)
            return await client.get_volume()

    async def set_mute(self, device_id: str, muted: bool) -> VolumeInfo:
        """Set mute state and return updated volume state."""
        async with self._device_client(device_id) as client:
            await client.set_mute(muted)
            return await client.get_volume()
