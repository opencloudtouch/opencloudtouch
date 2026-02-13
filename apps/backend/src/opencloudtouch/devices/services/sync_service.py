"""Device synchronization service.

Orchestrates device discovery and database synchronization.
"""

import logging
from typing import List, Optional

from opencloudtouch.db import Device
from opencloudtouch.devices.adapter import get_discovery_adapter, get_device_client
from opencloudtouch.devices.discovery.manual import ManualDiscovery
from opencloudtouch.devices.interfaces import IDeviceRepository
from opencloudtouch.devices.models import SyncResult
from opencloudtouch.discovery import DiscoveredDevice

logger = logging.getLogger(__name__)


class DeviceSyncService:
    """
    Orchestrates device discovery and database synchronization.

    Responsibilities:
    - Discover devices via SSDP and/or manual IPs
    - Query each device for detailed info
    - Persist device data to database
    - Track sync success/failure statistics
    """

    def __init__(
        self,
        repository: IDeviceRepository,
        discovery_timeout: int = 10,
        manual_ips: Optional[List[str]] = None,
        discovery_enabled: bool = True,
    ):
        """
        Initialize sync service.

        Args:
            repository: Device repository for persistence
            discovery_timeout: SSDP discovery timeout in seconds
            manual_ips: Optional list of manual device IPs
            discovery_enabled: Whether SSDP discovery is enabled
        """
        self.repository = repository
        self.discovery_timeout = discovery_timeout
        self.manual_ips = manual_ips or []
        self.discovery_enabled = discovery_enabled

    async def sync(self) -> SyncResult:
        """
        Discover devices and synchronize to database.

        Process:
        1. Discover via SSDP (if enabled)
        2. Discover via manual IPs (if configured)
        3. Query each device for detailed info (/info endpoint)
        4. Upsert device to database
        5. Return sync statistics

        Returns:
            SyncResult with discovery/sync statistics
        """
        discovered_devices = await self._discover_devices()
        synced, failed = await self._sync_devices_to_db(discovered_devices)

        return SyncResult(
            discovered=len(discovered_devices),
            synced=synced,
            failed=failed,
        )

    async def _discover_devices(self) -> List[DiscoveredDevice]:
        """
        Discover devices via all enabled methods.

        Returns:
            List of discovered devices (may contain duplicates)
        """
        devices: List[DiscoveredDevice] = []

        # SSDP Discovery
        if self.discovery_enabled:
            devices.extend(await self._discover_via_ssdp())

        # Manual IPs
        if self.manual_ips:
            devices.extend(await self._discover_via_manual_ips())

        logger.info(f"Discovered {len(devices)} devices total")
        return devices

    async def _discover_via_ssdp(self) -> List[DiscoveredDevice]:
        """
        Discover devices via SSDP network scan.

        Returns:
            List of discovered devices
        """
        try:
            discovery = get_discovery_adapter(timeout=self.discovery_timeout)
            discovered = await discovery.discover()
            logger.info(f"SSDP discovered {len(discovered)} devices")
            return discovered
        except Exception as e:
            logger.error(f"SSDP discovery failed: {e}")
            return []

    async def _discover_via_manual_ips(self) -> List[DiscoveredDevice]:
        """
        Discover devices via manually configured IPs.

        Returns:
            List of discovered devices
        """
        try:
            manual = ManualDiscovery(self.manual_ips)
            discovered = await manual.discover()
            logger.info(f"Manual discovery found {len(discovered)} devices")
            return discovered
        except Exception as e:
            logger.error(f"Manual discovery failed: {e}")
            return []

    async def _sync_devices_to_db(
        self, discovered: List[DiscoveredDevice]
    ) -> tuple[int, int]:
        """
        Query each discovered device and sync to database.

        Args:
            discovered: List of discovered devices

        Returns:
            Tuple of (synced_count, failed_count)
        """
        synced = 0
        failed = 0

        for discovered_device in discovered:
            try:
                device = await self._fetch_device_info(discovered_device)
                await self.repository.upsert(device)
                synced += 1
                logger.info(f"Synced device: {device.name} ({device.device_id})")
            except Exception as e:
                failed += 1
                device_info = getattr(discovered_device, "ip", str(discovered_device))
                logger.error(f"Failed to sync device {device_info}: {e}")

        return synced, failed

    async def _fetch_device_info(self, discovered: DiscoveredDevice) -> Device:
        """
        Query device for detailed info via /info endpoint.

        Args:
            discovered: Discovered device with base URL

        Returns:
            Device model with complete information

        Raises:
            Exception: If device query fails
        """
        client = get_device_client(discovered.base_url)
        info = await client.get_info()

        return Device(
            device_id=info.device_id,
            ip=discovered.ip,
            name=info.name,
            model=info.type,
            mac_address=info.mac_address,
            firmware_version=info.firmware_version,
        )
