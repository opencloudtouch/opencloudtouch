"""Device service - Business logic layer for device operations.

Orchestrates device discovery, synchronization, and management.
Separates HTTP layer (routes) from business logic from data layer (repository).
"""

import logging
from typing import List, Optional

from bosesoundtouchapi import SoundTouchClient, SoundTouchDevice

from opencloudtouch.db import Device
from opencloudtouch.devices.interfaces import (
    IDeviceRepository,
    IDeviceSyncService,
    IDiscoveryAdapter,
)
from opencloudtouch.devices.capabilities import (
    get_device_capabilities,
    get_feature_flags_for_ui,
)
from opencloudtouch.devices.models import SyncResult
from opencloudtouch.discovery import DiscoveredDevice

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
        logger.info(f"Starting device discovery (timeout: {timeout}s)")

        devices = await self.discovery_adapter.discover(timeout=timeout)

        logger.info(f"Discovery complete: {len(devices)} device(s) found")

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
            raise ValueError(f"Device not found: {device_id}")

        logger.info(f"Querying capabilities for device {device_id} ({device.ip})")

        try:
            # Create device client
            st_device = SoundTouchDevice(device.ip)
            client = SoundTouchClient(st_device)

            # Get capabilities
            capabilities = await get_device_capabilities(client)

            # Convert to UI-friendly format
            feature_flags = get_feature_flags_for_ui(capabilities)

            return feature_flags

        except Exception as e:
            logger.error(f"Failed to get capabilities for device {device_id}: {e}")
            raise

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
        logger.info(f"Pressing key {key} on device {device_id} (state: {state})")

        # Get device from DB
        device = await self.repository.get_by_device_id(device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")

        # Create client and press key
        from opencloudtouch.devices.adapter import get_device_client

        base_url = f"http://{device.ip}:8090"
        client = get_device_client(base_url)

        try:
            await client.press_key(key, state)
            logger.info(f"Successfully pressed key {key} on device {device_id}")
        finally:
            await client.close()

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
