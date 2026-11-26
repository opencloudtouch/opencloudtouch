"""Domain service for preset management.

This service encapsulates the business logic for managing preset mappings.
It separates concerns: Routes handle HTTP, Service handles business logic,
Repository handles data persistence.
"""

import asyncio
import ipaddress
import logging
import os
import socket
import time
from typing import TYPE_CHECKING, Any, List, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree.ElementTree import ParseError

import httpx
from defusedxml.ElementTree import fromstring as parse_xml_string

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    raise_coded,
)
from opencloudtouch.devices.client import StoredMusicItem
from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.parser import DevicePresetParser
from opencloudtouch.presets.repository import PresetRepository

# Small /navigate pages: one 1000-item request of a 1447-item parent took > 15 s
# and blocked the speaker's next /navigate (T22 2a/2b).
_BROWSE_PAGE = 50
_BROWSE_BUDGET = 60.0  # seconds for all pages of one save

if TYPE_CHECKING:
    from opencloudtouch.devices.client import NowPlayingInfo
    from opencloudtouch.dlna.service import DlnaService

logger = logging.getLogger(__name__)


async def fetch_device_presets(device_ip: str) -> bytes:
    """Fetch a speaker's /presets XML.

    Raises:
        DeviceConnectionError: If the device is unreachable
    """
    device_url = f"http://{device_ip}:{SOUNDTOUCH_HTTP_PORT}/presets"  # NOSONAR — Bose devices only support HTTP
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(device_url)
            response.raise_for_status()
    except httpx.HTTPError as e:
        raise DeviceConnectionError(device_ip, str(e)) from e
    return response.content


class PresetService:
    """Service for managing preset mappings.

    This service provides business logic for preset operations,
    ensuring separation between HTTP layer (routes) and data layer (repository).
    """

    def __init__(
        self,
        repository: PresetRepository,
        device_repository: DeviceRepository,
        dlna_service: "DlnaService | None" = None,
    ):
        """Initialize the preset service.

        Args:
            repository: PresetRepository instance for preset data persistence
            device_repository: DeviceRepository instance for device lookups
            dlna_service: DlnaService for native DLNA presets (folder check, cover)
        """
        self.repository = repository
        self.device_repository = device_repository
        self.dlna_service = dlna_service
        self._parser = DevicePresetParser()

    @staticmethod
    async def _validate_stream_url(
        url: str,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        """Validate HTTP(S) URL and return all safe DNS targets without fetching audio."""
        try:
            parsed = urlsplit(url.strip())
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Invalid stream URL") from exc

        if (
            parsed.scheme not in {"http", "https"}
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or port == 0
        ):
            raise ValueError("Stream URL must use HTTP or HTTPS")

        port = port if port is not None else (443 if parsed.scheme == "https" else 80)
        try:
            addresses = await asyncio.wait_for(
                asyncio.get_running_loop().getaddrinfo(
                    hostname, port, type=socket.SOCK_STREAM
                ),
                timeout=3.0,
            )
        except (OSError, TimeoutError) as exc:
            raise ValueError("Stream URL is not reachable") from exc

        ips = [ipaddress.ip_address(address[4][0]) for address in addresses]
        if not ips or any(not ip.is_global or ip.is_multicast for ip in ips):
            raise ValueError("Stream URL resolves to a non-public IP address")
        return list(dict.fromkeys(ips))

    @staticmethod
    async def _check_stream_reachable(url: str) -> None:
        """Check a manually entered stream before saving, including redirects."""
        current_url = url.strip()
        timeout = httpx.Timeout(5.0, connect=3.0)
        for _ in range(6):
            ips = await PresetService._validate_stream_url(current_url)
            parsed = urlsplit(current_url)
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            extensions = (
                {"sni_hostname": parsed.hostname} if parsed.scheme == "https" else {}
            )
            redirect_url = None

            for ip in ips:
                ip_host = f"[{ip}]" if ip.version == 6 else str(ip)
                pinned_url = urlunsplit(
                    (
                        parsed.scheme,
                        f"{ip_host}:{port}",
                        parsed.path or "/",
                        parsed.query,
                        "",
                    )
                )
                try:
                    async with httpx.AsyncClient(
                        timeout=timeout, follow_redirects=False, trust_env=False
                    ) as client:
                        async with client.stream(
                            "GET",
                            pinned_url,
                            headers={"Host": parsed.netloc},
                            extensions=extensions,
                        ) as response:
                            if response.status_code in {301, 302, 303, 307, 308}:
                                location = response.headers.get("location")
                                if not location:
                                    raise ValueError("Stream URL is not reachable")
                                redirect_url = urljoin(current_url, location)
                                break
                            response.raise_for_status()
                            return
                except httpx.RequestError:
                    # Try another verified DNS address if this one cannot connect.
                    continue
                except httpx.HTTPStatusError as exc:
                    raise ValueError("Stream URL is not reachable") from exc

            if redirect_url is None:
                raise ValueError("Stream URL is not reachable")
            current_url = redirect_url
        raise ValueError("Too many stream URL redirects")

    async def set_preset(
        self,
        device_id: str,
        preset_number: int,
        station_uuid: str,
        station_name: str,
        station_url: str,
        station_homepage: Optional[str] = None,
        station_favicon: Optional[str] = None,
    ) -> Preset:
        """Set a preset for a device.

        Creates or updates a preset mapping AND programs the Bose device.
        This ensures the physical preset button will play the configured station.

        Args:
            device_id: Device identifier
            preset_number: Preset number (1-6)
            station_uuid: RadioBrowser station UUID
            station_name: Station name
            station_url: Stream URL
            station_homepage: Optional station homepage URL
            station_favicon: Optional station favicon URL

        Returns:
            The saved Preset object

        Raises:
            ValueError: If preset_number is not between 1-6
            DeviceNotFoundError: If the device is unknown
            DeviceConnectionError: If the speaker is unreachable (nothing is saved)
        """
        if station_uuid.startswith("manual-"):
            await self._check_stream_reachable(station_url)

        # 1. Program the speaker first: if it is unreachable this raises
        # DeviceConnectionError and nothing is saved, so OCT and speaker stay in sync.
        device = await self.device_repository.get_by_device_id(device_id)
        if not device:
            raise DeviceNotFoundError(device_id)

        from opencloudtouch.core.config import get_config
        from opencloudtouch.devices.adapter import get_device_client

        base_url = f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR — Bose devices only support HTTP
        client = get_device_client(base_url)
        try:
            await client.store_preset(
                device_id=device_id,
                preset_number=preset_number,
                station_url=station_url,
                station_name=station_name,
                oct_backend_url=get_config().station_descriptor_base_url,
                station_image_url=station_favicon or "",
                station_uuid=station_uuid,
            )
        finally:
            await client.close()
        logger.info(
            "Bose device programmed: Preset %d = %s", preset_number, station_name
        )

        # 2. Save to the OpenCloudTouch database
        preset = Preset(
            device_id=device_id,
            preset_number=preset_number,
            station_uuid=station_uuid,
            station_name=station_name,
            station_url=station_url,
            station_homepage=station_homepage,
            station_favicon=station_favicon,
            source="LOCAL_INTERNET_RADIO",  # OCT-managed presets from RadioBrowser
        )
        saved_preset = await self.repository.set_preset(preset)
        logger.info(
            "Set preset %d in database for device %s: %s",
            preset_number,
            device_id,
            station_name,
        )

        return saved_preset

    async def set_dlna_preset(
        self,
        device_id: str,
        preset_number: int,
        server_id: str,
        parent_id: str,
        object_id: str,
        confirm: bool = False,
    ) -> Preset:
        """Save a DLNA folder/track as a native preset (speaker first, then DB).

        The ContentItem is stored exactly as the speaker's /navigate returned it.

        Raises:
            DeviceNotFoundError: If the device is unknown
            DeviceConnectionError: If the speaker is unreachable (nothing is saved)
            CodedApiError: 404 object not found, 409 folder without audio first
                (unless confirm), 502 speaker/server error
        """
        from opencloudtouch.devices.adapter import get_device_client

        if self.dlna_service is None:
            raise RuntimeError("PresetService has no DlnaService")
        device = await self.device_repository.get_by_device_id(device_id)
        if not device:
            raise DeviceNotFoundError(device_id)

        base_url = f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR
        client = get_device_client(base_url)
        try:
            item = await self._find_speaker_item(
                client, server_id, parent_id, object_id
            )
            if (
                item.is_directory
                and not confirm
                and not await self._dlna(
                    self.dlna_service.first_child_is_audio(server_id, object_id)
                )
            ):
                raise_coded(
                    409,
                    error_codes.DLNA_FOLDER_NO_AUDIO_FIRST,
                    "Folder does not start with an audio item",
                    extra={"title": item.item_name},
                )
            artwork = await self._dlna_artwork(self.dlna_service, server_id, object_id)
            await client.store_native_preset(preset_number, item, artwork or "")
        finally:
            await client.close()

        return await self.repository.set_preset(
            Preset(
                device_id=device_id,
                preset_number=preset_number,
                station_uuid=f"STORED_MUSIC_{preset_number}",
                station_name=item.item_name,
                station_url=item.location,
                station_favicon=artwork,
                source="STORED_MUSIC",
                source_account=item.source_account,
            )
        )

    @staticmethod
    async def _dlna(call: Any) -> Any:
        """Await a DlnaService call; map its failures to coded API errors."""
        from opencloudtouch.dlna.client import DlnaBrowseError
        from opencloudtouch.dlna.errors import classify

        try:
            return await call
        except (DlnaBrowseError, LookupError) as exc:
            status, code, detail = classify(exc)
            raise_coded(status, code, detail)

    @staticmethod
    async def _find_speaker_item(
        client: Any, server_id: str, parent_id: str, object_id: str
    ) -> StoredMusicItem:
        """Find the speaker's own ContentItem for the object, page by page.

        1602 is retried in the client.
        """
        deadline = time.monotonic() + _BROWSE_BUDGET
        start = 1
        while True:
            if time.monotonic() > deadline:
                raise_coded(
                    504, error_codes.DLNA_SERVER_TIMEOUT, "Speaker browse timed out"
                )
            browse = await client.browse_stored_music(
                f"{server_id}/0",
                None if parent_id == "0" else parent_id,
                start,
                _BROWSE_PAGE,
            )
            if browse.error_code is not None:
                raise_coded(
                    502,
                    error_codes.DLNA_UPSTREAM_ERROR,
                    "Speaker could not browse server",
                )
            for item in browse.items:
                if item.location.removesuffix(" TRACK") == object_id:
                    return item
            start += _BROWSE_PAGE
            # shortcut: without <totalItems>, a page shortened by skipped items
            # ends the search early; the real speaker reports the total.
            if len(browse.items) < _BROWSE_PAGE or (
                browse.total is not None and start > browse.total
            ):
                raise_coded(404, error_codes.DLNA_OBJECT_NOT_FOUND, "Object not found")

    @staticmethod
    async def _dlna_artwork(
        dlna: "DlnaService", server_id: str, object_id: str
    ) -> Optional[str]:
        """Cover URL of the object if it is on the media server's own host."""
        from opencloudtouch.dlna.client import DlnaBrowseError

        try:
            server = await dlna.resolve(server_id)
            art = (await dlna.get_object_path(server_id, object_id)).item.album_art_url
        except (DlnaBrowseError, LookupError):
            return None
        parts = urlsplit(art or "")
        host = urlsplit(server.control_url).hostname
        if parts.scheme in ("http", "https") and parts.hostname == host:
            return art
        return None

    async def get_preset(self, device_id: str, preset_number: int) -> Optional[Preset]:
        """Get a specific preset for a device.

        Args:
            device_id: Device identifier
            preset_number: Preset number (1-6)

        Returns:
            The Preset object if found, None otherwise
        """
        return await self.repository.get_preset(device_id, preset_number)

    async def get_all_presets(self, device_id: str, live: bool = False) -> List[Preset]:
        """Get all presets for a device; empty slots are not included.

        Internal enrichment and matching read the stored OCT rows only. With
        ``live`` (the public GET route, I-2) the speaker's /presets is imported
        first: IF the speaker cannot be read THEN the OCT rows are returned
        unchanged and a warning is logged. Mock speakers keep presets only in
        OCT (their store_preset is a no-op), so mock mode never reads them.
        """
        if live and os.getenv("OCT_MOCK_MODE", "false").lower() != "true":
            try:
                await self.sync_presets_from_device(device_id)
            # ValueError covers defusedxml's rejection of unsafe XML
            except (
                DeviceNotFoundError,
                DeviceConnectionError,
                ParseError,
                ValueError,
            ) as exc:
                logger.warning(
                    "Speaker presets unreadable for %s, serving OCT rows: %s",
                    device_id,
                    type(exc).__name__,
                )
        return await self.repository.get_all_presets(device_id)

    async def clear_preset(self, device_id: str, preset_number: int) -> bool:
        """Clear a specific preset for a device.

        Args:
            device_id: Device identifier
            preset_number: Preset number (1-6)

        Returns:
            True if preset was deleted, False if it didn't exist
        """
        await self._remove_on_device(device_id, preset_number)
        result = await self.repository.clear_preset(device_id, preset_number)

        if result:
            logger.info(  # NOSONAR
                "Cleared preset %d for device %s", preset_number, device_id
            )

        return bool(result)

    async def clear_all_presets(self, device_id: str) -> int:
        """Clear all presets for a device.

        Args:
            device_id: Device identifier

        Returns:
            Number of presets deleted
        """
        for preset in await self.repository.get_all_presets(device_id):
            await self._remove_on_device(device_id, preset.preset_number)
        count = await self.repository.clear_all_presets(device_id)

        logger.info("Cleared %d presets for device %s", count, device_id)  # NOSONAR

        return count

    async def sync_presets_from_device(self, device_id: str) -> int:
        """Sync presets from physical device to OCT database.

        Fetches presets from device's /presets endpoint and imports them into OCT.
        This is useful when a device was configured by another OCT instance or manually.

        Args:
            device_id: Device identifier

        Returns:
            Number of presets synced

        Raises:
            ValueError: If device not found
            httpx.HTTPError: If device is unreachable
        """
        device = await self.device_repository.get_by_device_id(device_id)
        if not device:
            raise DeviceNotFoundError(device_id)
        # Mock speakers keep presets only in OCT: there is no /presets to read.
        if os.getenv("OCT_MOCK_MODE", "false").lower() == "true":
            return 0

        logger.info(
            "Syncing presets from device %s (%s)",
            device_id,
            device.ip,
            extra={"device_id": device_id, "device_ip": device.ip},
        )

        root = parse_xml_string(await self._fetch_device_presets(device.ip))
        slots_on_device = [elem.get("id") for elem in root.findall("preset")]
        parsed_presets = [
            preset
            for elem in root.findall("preset")
            if (preset := self._parser.parse_element(elem, device_id))
        ]
        synced_count = 0

        for preset in parsed_presets:
            existing = await self.repository.get_preset(device_id, preset.preset_number)
            if existing and existing.station_url == preset.station_url:
                # Same item: OCT keeps its metadata and identity (decision 9, L5, N2).
                preset.station_uuid = existing.station_uuid
                preset.source = existing.source
                preset.station_homepage = existing.station_homepage
                preset.station_favicon = (
                    preset.station_favicon or existing.station_favicon
                )
                if preset.source == "STORED_MUSIC" and not preset.source_account:
                    # Repairs only an account OCT's own /full dropped (T22 5c).
                    preset.source_account = existing.source_account
            await self.repository.set_preset(preset)
            synced_count += 1
            logger.info(
                "Synced preset %d: %s (source: %s)",
                preset.preset_number,
                preset.station_name,
                preset.source,
                extra={
                    "device_id": device_id,
                    "preset_number": preset.preset_number,
                    "source": preset.source,
                },
            )

        # The device is the source of truth: drop OCT slots the device does not have;
        # a slot it has but OCT cannot read keeps its OCT row (L3).
        for slot in range(1, 7):
            if str(slot) not in slots_on_device:
                await self.repository.clear_preset(device_id, slot)

        logger.info(
            "Synced %d presets from device %s",
            synced_count,
            device_id,
            extra={"device_id": device_id, "synced_count": synced_count},
        )
        return synced_count

    async def _remove_on_device(self, device_id: str, preset_number: int) -> None:
        """Clear a slot on the speaker.

        Raises whatever the speaker call raises (for example DeviceConnectionError
        when it is offline), so the caller can leave the OCT database untouched.
        """
        from opencloudtouch.devices.adapter import get_device_client

        device = await self.device_repository.get_by_device_id(device_id)
        if not device:
            return
        # SoundTouch speakers only speak plain HTTP on the LAN
        base_url = f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR
        client = get_device_client(base_url)
        try:
            await client.remove_preset(preset_number)
        finally:
            await client.close()

    _fetch_device_presets = staticmethod(fetch_device_presets)


async def match_stored_music_preset(
    result: dict[str, object],
    info: "NowPlayingInfo",
    device_id: str,
    preset_service: PresetService,
) -> Preset | None:
    """Mark the slot whose ContentItem matches location + account (decision 31).

    Reads the stored rows (no speaker read); never matched by station name; the
    UDN is compared case-insensitively.
    """
    if not info.location or not info.source_account:
        return None
    account = info.source_account.casefold()
    try:
        presets = await preset_service.get_all_presets(device_id)
    except Exception:
        logger.debug(
            "[NowPlaying] Preset lookup failed for %s", device_id, exc_info=True
        )
        return None
    match = next(
        (
            p
            for p in presets
            if p.station_url == info.location
            and (p.source_account or "").casefold() == account
        ),
        None,
    )
    if match:
        result["preset_number"] = match.preset_number
        if not result["artwork_url"] and match.station_favicon:
            result["artwork_url"] = match.station_favicon
    return match
