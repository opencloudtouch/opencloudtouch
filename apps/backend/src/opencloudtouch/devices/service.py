"""Device service - Business logic layer for device operations.

Orchestrates device discovery, synchronization, and management.
Separates HTTP layer (routes) from business logic from data layer (repository).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, List, Optional, Union

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    DomainValidationError,
    raise_coded,
)
from opencloudtouch.db import Device
from opencloudtouch.devices.adapter import get_device_client
from opencloudtouch.devices.capabilities import (
    get_capabilities_for_ip,
    get_feature_flags_for_ui,
    merge_bass_capabilities,
)
from opencloudtouch.devices.client import (
    BassInfo,
    NowPlayingInfo,
    VolumeInfo,
)
from opencloudtouch.devices.device_settings import (
    DeviceSettings,
    SettingWriteResult,
    validate_enabled,
    validate_language_id,
    validate_time_format,
    validate_timezone,
)
from opencloudtouch.devices.events import DiscoveryEvent, DiscoveryEventType
from opencloudtouch.devices.interfaces import (
    IDeviceRepository,
    IDeviceSyncService,
    IDiscoveryAdapter,
)
from opencloudtouch.devices.models import KEY_MAPPING, KeyType, SyncResult
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT, DiscoveredDevice

logger = logging.getLogger(__name__)

# Seconds a single settings read may take before the setting counts as unavailable
_SETTING_READ_TIMEOUT: float = 5.0

# Type for post-sync callback: async (device_id, ip) → None
OnDeviceSynced = Optional[Callable[[str, str], Any]]


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
        # Per-device write locks for device settings (created lazily, one per device)
        self._setting_locks: dict[str, asyncio.Lock] = {}
        self.sync_service = sync_service
        self.discovery_adapter = discovery_adapter
        self._on_device_synced: OnDeviceSynced = None

    def set_on_device_synced(self, callback) -> None:
        """Register callback invoked after each device sync: callback(device_id, ip)."""
        self._on_device_synced = callback

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

        # Notify WS manager of synced devices (IP change → reconnect)
        if self._on_device_synced:
            await self._notify_ws_for_synced_devices()

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

            # Notify WS manager of synced devices (IP change → reconnect)
            if self._on_device_synced:
                await self._notify_ws_for_synced_devices()

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

    async def probe_single_device(self, ip: str) -> Device:
        """Probe a single device by IP, fetch its info, and upsert to DB.

        Args:
            ip: IP address of the device

        Returns:
            Device model with complete information

        Raises:
            Exception: If device is not reachable or sync fails
        """
        discovered = DiscoveredDevice(ip=ip, port=SOUNDTOUCH_HTTP_PORT)
        device = await self.sync_service.fetch_and_upsert_one(discovered)
        return device

    async def _notify_ws_for_synced_devices(self) -> None:
        """Call on_device_synced for all known devices (IP change → reconnect)."""
        try:
            devices = await self.repository.get_all()
            for device in devices:
                if device.ip and self._on_device_synced:
                    await self._on_device_synced(device.device_id, device.ip)
        except Exception:
            logger.exception("Failed to notify WS manager of synced devices")

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
        """Get persisted device capabilities for UI feature detection."""
        device = await self.repository.get_by_device_id(device_id)
        if not device:
            raise DeviceNotFoundError(device_id)

        if device.capabilities is not None:
            return device.capabilities

        # Backward-compatible fallback for devices stored before capability
        # persistence was introduced. Re-discovery will persist the result.
        logger.info("No stored capabilities for %s; querying device", device_id)
        detected = await get_capabilities_for_ip(device.ip)
        flags = get_feature_flags_for_ui(detected)

        client = None
        try:
            base_url = f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR — Bose devices only support HTTP
            client = await asyncio.to_thread(get_device_client, base_url)
            bass = await client.get_bass_capabilities()
        except Exception:
            logger.debug(
                "Could not fetch bass capabilities for %s",
                device_id,
                exc_info=True,
            )
        else:
            merge_bass_capabilities(flags, bass)
        finally:
            if client is not None:
                await client.close()

        return flags

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

    async def get_device_bass(self, device_id: str) -> BassInfo:
        """Get current bass state from a device."""
        async with self._device_client(device_id) as client:
            return await client.get_bass()

    async def set_device_bass(self, device_id: str, level: int) -> None:
        """Validate against discovered capabilities and set bass on the device."""
        capabilities = await self.get_device_capabilities(device_id)
        bass = capabilities.get("settings", {}).get("bass")

        if not bass or not bass.get("available", False):
            raise ValueError("Bass control is not available on this device")

        minimum = bass.get("minimum")
        maximum = bass.get("maximum")
        if minimum is None or maximum is None:
            raise ValueError("Bass range is not available for this device")
        if level < minimum or level > maximum:
            raise ValueError(f"Bass level must be between {minimum} and {maximum}")

        async with self._device_client(device_id) as client:
            await client.set_bass(level)

    # --- Device settings (language, clock, power saving) -------------------

    async def _read_setting(
        self, name: str, getter: Callable[[], Awaitable[Any]]
    ) -> Any:
        """Read one setting; None if it is unavailable or unreadable.

        Only an unreachable device (DeviceConnectionError) propagates.
        """
        try:
            async with asyncio.timeout(_SETTING_READ_TIMEOUT):
                return await getter()
        except DeviceConnectionError:
            raise
        except NotImplementedError:
            return None
        except (
            Exception
        ) as e:  # noqa: BLE001 - one broken setting must not fail the rest
            # The device id comes from the request path: keep it out of the log line
            logger.warning("Setting %s unreadable (%s)", name, type(e).__name__)
            return None

    async def get_device_settings(self, device_id: str) -> DeviceSettings:
        """Read language, clock and power saving independently of each other.

        Raises:
            DeviceConnectionError: if the device is unreachable for all three reads.
        """
        async with self._device_client(device_id) as client:
            results = await asyncio.gather(
                self._read_setting("language", client.get_language),
                self._read_setting("clock", client.get_clock),
                self._read_setting("power_saving", client.get_power_saving),
                return_exceptions=True,
            )
        failures = [r for r in results if isinstance(r, DeviceConnectionError)]
        if len(failures) == len(results):
            raise failures[0]
        language, clock, power_saving = (
            None if isinstance(r, BaseException) else r for r in results
        )
        return DeviceSettings(language=language, clock=clock, power_saving=power_saving)

    async def _write_setting(
        self,
        device_id: str,
        name: str,
        write: Callable[[Any, Any], Awaitable[None]],
        is_applied: Callable[[Any], bool],
    ) -> SettingWriteResult:
        """Pre-read (409 if unavailable), POST, post-read (verifies what was kept)."""
        lock = self._setting_locks.setdefault(device_id, asyncio.Lock())
        async with lock, self._device_client(device_id) as client:
            getter = getattr(client, f"get_{name}")
            before = await self._read_setting(name, getter)
            if before is None:
                raise_coded(
                    409,
                    error_codes.SETTING_NOT_AVAILABLE,
                    f"Setting '{name}' is not available on this device",
                )
            await write(client, before)
            try:
                after = await self._read_setting(name, getter)
            except DeviceConnectionError:
                after = None
            return SettingWriteResult(
                applied=after is not None and is_applied(after), value=after
            )

    async def set_device_language(
        self, device_id: str, language_id: Any
    ) -> SettingWriteResult:
        """Set the display language and report whether the speaker kept it."""
        wanted = validate_language_id(language_id)

        async def write(client: Any, _before: Any) -> None:
            await client.set_language(wanted)

        return await self._write_setting(
            device_id, "language", write, lambda after: after.id == wanted
        )

    async def set_device_clock(
        self, device_id: str, enabled: Any, time_format: Any, timezone: Any
    ) -> SettingWriteResult:
        """Set the standby clock (read-modify-write) and verify the result."""
        is_on = validate_enabled(enabled)
        if is_on:
            wanted_format = validate_time_format(time_format)
            wanted_zone = validate_timezone(timezone)

        async def write(client: Any, before: Any) -> None:
            if is_on:
                await client.set_clock(
                    True, wanted_format, wanted_zone, dict(before.extra)
                )
            else:  # only userEnable changes: re-send what was read
                await client.set_clock(
                    False, before.time_format, before.timezone, dict(before.extra)
                )

        def is_applied(after: Any) -> bool:
            if not is_on:
                return after.enabled is False
            return (
                after.enabled is True
                and after.time_format == wanted_format
                and after.timezone == wanted_zone
            )

        return await self._write_setting(device_id, "clock", write, is_applied)

    async def set_device_power_saving(
        self, device_id: str, enabled: Any
    ) -> SettingWriteResult:
        """Switch power saving on or off and verify the result."""
        wanted = validate_enabled(enabled)

        async def write(client: Any, _before: Any) -> None:
            await client.set_power_saving(wanted)

        return await self._write_setting(
            device_id, "power_saving", write, lambda after: after.enabled is wanted
        )

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

    async def reboot_device(self, device_id: str) -> None:
        """Send reboot command to device."""
        async with self._device_client(device_id) as client:
            await client.reboot()
