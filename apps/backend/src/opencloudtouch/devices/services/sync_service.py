"""Device synchronization service.

Orchestrates device discovery and database synchronization.
"""

import logging
from typing import TYPE_CHECKING, List, Optional

from opencloudtouch.db import Device
from opencloudtouch.devices.adapter import get_device_client, get_discovery_adapter
from opencloudtouch.devices.discovery.manual import ManualDiscovery
from opencloudtouch.devices.events import (
    device_failed_event,
    device_found_event,
    device_synced_event,
)
from opencloudtouch.devices.interfaces import IDeviceRepository
from opencloudtouch.devices.models import SyncResult
from opencloudtouch.discovery import DiscoveredDevice

if TYPE_CHECKING:
    from opencloudtouch.settings.repository import SettingsRepository

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
        settings_repo: Optional["SettingsRepository"] = None,
    ):
        """
        Initialize sync service.

        Args:
            repository: Device repository for persistence
            discovery_timeout: SSDP discovery timeout in seconds
            manual_ips: Optional list of manual device IPs (startup / env-var fallback)
            discovery_enabled: Whether SSDP discovery is enabled
            settings_repo: Optional SettingsRepository. When provided, manual IPs
                           are read from the DB at each sync so that IPs added via
                           the UI are picked up without a container restart.
        """
        self.repository = repository
        self.discovery_timeout = discovery_timeout
        self.manual_ips = manual_ips or []
        self.discovery_enabled = discovery_enabled
        self.settings_repo = settings_repo

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

    async def sync_with_events(self, event_bus) -> SyncResult:
        """
        Discover devices and synchronize to database with event streaming.

        Same as sync() but publishes events for SSE progressive loading.

        Args:
            event_bus: DiscoveryEventBus for publishing events

        Returns:
            SyncResult with discovery/sync statistics
        """
        discovered_devices = await self._discover_devices()

        # Publish device_found events
        for device in discovered_devices:
            await event_bus.publish(device_found_event(device))

        # Sync devices to DB with events
        synced = 0
        failed = 0

        async def _on_synced(device: Device) -> None:
            await event_bus.publish(device_synced_event(device))

        async def _on_failed(discovered: DiscoveredDevice, error: Exception) -> None:
            device_ip = getattr(discovered, "ip", str(discovered))
            await event_bus.publish(device_failed_event(device_ip, str(error)))

        for discovered_device in discovered_devices:
            if await self._sync_one_device(discovered_device, _on_synced, _on_failed):
                synced += 1
            else:
                failed += 1

        return SyncResult(
            discovered=len(discovered_devices),
            synced=synced,
            failed=failed,
        )

    async def _discover_devices(self) -> List[DiscoveredDevice]:
        """
        Discover devices via all enabled methods.

        Deduplicates results by IP address so that a device present in both
        SSDP and manual-IP lists is only synced once.

        Returns:
            Deduplicated list of discovered devices
        """
        devices: List[DiscoveredDevice] = []

        logger.debug(
            "Discovery config: ssdp=%s, manual_ips=%s, settings_repo=%s",
            self.discovery_enabled,
            bool(self.manual_ips),
            bool(self.settings_repo),
        )

        # SSDP Discovery
        if self.discovery_enabled:
            devices.extend(await self._discover_via_ssdp())

        # Manual IPs — always call when settings_repo is present (DB is authoritative),
        # otherwise only when the static startup list is non-empty.
        if self.settings_repo is not None or self.manual_ips:
            devices.extend(await self._discover_via_manual_ips())

        # Deduplicate by IP (SSDP and manual can surface the same device)
        seen_ips: set[str] = set()
        unique_devices: List[DiscoveredDevice] = []
        for device in devices:
            if device.ip not in seen_ips:
                seen_ips.add(device.ip)
                unique_devices.append(device)
            else:
                logger.debug(
                    f"Deduplicating device at {device.ip} (already found via another source)"
                )

        if len(unique_devices) < len(devices):
            logger.info(
                f"Deduplicated {len(devices) - len(unique_devices)} device(s) "
                f"({len(unique_devices)} unique after deduplication)"
            )

        logger.info(f"Discovered {len(unique_devices)} unique devices total")
        return unique_devices

    async def _discover_via_ssdp(self) -> List[DiscoveredDevice]:
        """
        Discover devices via SSDP network scan.

        Returns:
            List of discovered devices
        """
        try:
            discovery = get_discovery_adapter(timeout=self.discovery_timeout)
            discovered = await discovery.discover(timeout=self.discovery_timeout)
            logger.info(f"SSDP discovered {len(discovered)} devices")
            for d in discovered:
                logger.debug(
                    "SSDP device: ip=%s, name=%s", d.ip, getattr(d, "name", "?")
                )
            return discovered
        except Exception as e:
            logger.error(f"SSDP discovery failed: {e}")
            return []

    async def _discover_via_manual_ips(self) -> List[DiscoveredDevice]:
        """
        Discover devices via manually configured IPs.

        When a SettingsRepository is available, the IP list is fetched from the
        DB at call time so that IPs added via the UI are included without a
        container restart. Falls back to the static startup list otherwise.

        Returns:
            List of discovered devices
        """
        try:
            if self.settings_repo is not None:
                ips = await self.settings_repo.get_manual_ips()
                logger.info(f"Manual IPs from DB: {ips}")
            else:
                ips = self.manual_ips

            manual = ManualDiscovery(ips)
            discovered = await manual.discover()
            logger.info(f"Manual discovery found {len(discovered)} devices")
            for d in discovered:
                logger.debug(
                    "Manual device: ip=%s, name=%s", d.ip, getattr(d, "name", "?")
                )
            return discovered
        except Exception as e:
            logger.error(f"Manual discovery failed: {e}")
            return []

    async def _sync_devices_to_db(
        self, discovered: List[DiscoveredDevice]
    ) -> tuple[int, int]:
        """Query each discovered device and sync to database.

        Args:
            discovered: List of discovered devices

        Returns:
            Tuple of (synced_count, failed_count)
        """
        synced = 0
        failed = 0

        for discovered_device in discovered:
            if await self._sync_one_device(discovered_device):
                synced += 1
            else:
                failed += 1

        return synced, failed

    async def _sync_one_device(
        self,
        discovered: DiscoveredDevice,
        on_synced=None,
        on_failed=None,
    ) -> bool:
        """Fetch and upsert a single device.

        Encapsulates the fetch → upsert → log → callback flow used by
        both ``_sync_devices_to_db`` and ``sync_with_events``.

        Args:
            discovered: Discovered device to sync
            on_synced: Optional async callback(device) called on success
            on_failed: Optional async callback(discovered, error) called on failure

        Returns:
            True if sync succeeded, False otherwise
        """
        try:
            device = await self._fetch_device_info(discovered)
            await self.repository.upsert(device)
            logger.info(f"Synced device: {device.name} ({device.device_id})")
            if on_synced:
                await on_synced(device)
            return True
        except Exception as e:
            device_ip = getattr(discovered, "ip", str(discovered))
            logger.error(f"Failed to sync device {device_ip}: {e}")
            if on_failed:
                await on_failed(discovered, e)
            return False

    async def _fetch_device_info(self, discovered: DiscoveredDevice) -> Device:
        """
        Query device for detailed info via /info endpoint.

        Also fetches the margeAccountUUID from the device so that
        /streaming/account/{account_id}/full can resolve the correct device.

        Args:
            discovered: Discovered device with base URL

        Returns:
            Device model with complete information

        Raises:
            Exception: If device query fails
        """
        client = get_device_client(discovered.base_url)
        info = await client.get_info()

        # Fetch margeAccountUUID separately (parsed from /info XML)
        marge_uuid = await self._fetch_marge_account_uuid(discovered.ip)

        return Device(
            device_id=info.device_id,
            ip=discovered.ip,
            name=info.name,
            model=info.type,
            mac_address=info.mac_address,
            firmware_version=info.firmware_version,
            marge_account_uuid=marge_uuid,
        )

    @staticmethod
    async def _fetch_marge_account_uuid(device_ip: str) -> Optional[str]:
        """Fetch margeAccountUUID from device /info endpoint.

        Uses the existing account_pairing_service function which
        parses the raw /info XML for the <margeAccountUUID> element.

        Returns:
            The UUID string if present, None otherwise.
            Never raises — logs warnings on failure.
        """
        try:
            from opencloudtouch.setup.account_pairing_service import (
                check_marge_account_uuid,
            )

            return await check_marge_account_uuid(device_ip)
        except Exception:
            logger.debug(
                "Could not fetch margeAccountUUID from %s", device_ip, exc_info=True
            )
            return None
