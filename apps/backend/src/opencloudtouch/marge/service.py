"""Marge account sync service.

Orchestrates preset and recents data for Bose streaming.bose.com
account sync protocol. Keeps route handlers thin.
"""

import base64
import json
import logging
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

from opencloudtouch.core.source_types import BASE_SOURCES
from opencloudtouch.devices.adapter import get_device_client
from opencloudtouch.devices.client import DeviceClient
from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT
from opencloudtouch.marge.source_repository import (
    MargeSourceRepository,
    MediaServerSource,
)
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.parser import preset_from_content_item
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.recents.models import RecentPlay
from opencloudtouch.recents.repository import RecentsRepository

logger = logging.getLogger(__name__)


def _station_from_location(source: str, location: str, name: str) -> tuple[str, str]:
    """Stream URL and artwork behind a preset location the speaker reports.

    OCT hands out Orion adapter locations (``...station?data=<base64 json>``) for
    its own stations; storing that URL again would wrap it twice, so unwrap it.
    """
    if source != "TUNEIN":
        data = parse_qs(urlparse(location).query).get("data")
        if data:
            try:
                decoded = json.loads(base64.b64decode(data[0]))
                return (
                    decoded.get("streamUrl") or location,
                    decoded.get("imageUrl") or "",
                )
            except (ValueError, AttributeError):
                logger.warning("[MARGE] Undecodable Orion location for preset %s", name)
    return location, ""


class MargeService:
    """Orchestrates account data assembly for Bose device sync."""

    def __init__(
        self,
        preset_repo: PresetRepository,
        recents_repo: RecentsRepository,
        device_repo: Optional[DeviceRepository] = None,
        source_repo: Optional[MargeSourceRepository] = None,
        client_factory: Callable[[str], DeviceClient] = get_device_client,
    ) -> None:
        self._preset_repo = preset_repo
        self._recents_repo = recents_repo
        self._device_repo = device_repo
        self._source_repo = source_repo
        self._client_factory = client_factory

    async def resolve_device_id_for_account(self, account_id: str) -> Optional[str]:
        """Resolve account_id (margeAccountUUID) to device_id (MAC).

        Args:
            account_id: The marge account UUID from the streaming request

        Returns:
            device_id if found, None otherwise
        """
        if not self._device_repo:
            logger.warning(  # NOSONAR
                "[MARGE] No device_repo - cannot resolve account %s",
                account_id,
            )
            return None

        device = await self._device_repo.get_by_account_uuid(account_id)
        if device:
            logger.info(  # NOSONAR — internal device mapping
                "[MARGE] Resolved account %s -> device %s (%s)",
                account_id,
                device.device_id,
                device.name,
            )
            return device.device_id

        # Fallback: account_id might be the device_id itself (MAC address)
        device = await self._device_repo.get_by_device_id(account_id)
        if device:
            logger.info(  # NOSONAR
                "[MARGE] Fallback: account_id %s is device_id (%s)",
                account_id,
                device.name,
            )
            return device.device_id

        logger.warning(  # NOSONAR
            "[MARGE] No device found for account UUID %s", account_id
        )
        return None

    async def get_full_account(
        self, device_id: str
    ) -> tuple[list[Preset], list[RecentPlay]]:
        """Get full account data (presets + recents) for a device.

        Returns:
            Tuple of (presets, recents)
        """
        presets = await self._preset_repo.get_all_presets(device_id)
        recents = await self._recents_repo.get_recents(device_id)
        logger.info(  # NOSONAR — internal IDs
            "[MARGE] Account sync: %d presets, %d recents for %s",
            len(presets),
            len(recents),
            device_id,
        )
        return presets, recents

    async def get_presets(self, device_id: str) -> list[Preset]:
        """Get presets for a device."""
        return await self._preset_repo.get_all_presets(device_id)

    async def add_recent(self, recent: RecentPlay) -> RecentPlay:
        """Store a recent the speaker reported (upserts by location)."""
        return await self._recents_repo.add_recent(recent)

    async def get_recents(self, device_id: str) -> list[RecentPlay]:
        """Get recently played items for a device."""
        return await self._recents_repo.get_recents(device_id)

    async def rename_device(self, device_id: str, name: str) -> bool:
        """Take over the name a speaker reports; False if the device is unknown."""
        if not self._device_repo:
            return False
        return await self._device_repo.update_name(device_id, name)

    async def store_preset(
        self,
        device_id: str,
        slot: int,
        source_id: str,
        name: str,
        location: str,
        source_account: str | None = None,
    ) -> Preset:
        """Store a preset the speaker wrote (upsert; keeps uuid and homepage of the slot)."""
        source = next(
            (s.source_type for s in BASE_SOURCES if s.streaming_id == source_id),
            source_id,
        )
        stored = (
            await self._stored_source(device_id, source_id)
            if source == source_id
            else None
        )
        if stored:
            source = "STORED_MUSIC"
        existing = await self._preset_repo.get_preset(device_id, slot)
        account = source_account or (stored.account if stored else None)
        if (
            not account
            and source == "STORED_MUSIC"
            and existing
            and existing.station_url == location
        ):
            # Same item without account: OCT's own /full dropped it (T22 5c).
            account = existing.source_account
        if source == "STORED_MUSIC" and account:
            # Same importer as "Load from device" (decision 28).
            imported = preset_from_content_item(
                device_id,
                slot,
                source,
                location,
                account,
                name,
                existing.station_favicon
                if existing and existing.station_url == location
                else None,
            )
            if imported:
                return await self._preset_repo.set_preset(imported)
        station_url, art = _station_from_location(source, location, name)
        return await self._preset_repo.set_preset(
            Preset(
                device_id=device_id,
                preset_number=slot,
                station_uuid=(existing.station_uuid if existing else f"marge_{slot}"),
                station_name=name,
                station_url=station_url,
                station_homepage=existing.station_homepage if existing else None,
                station_favicon=art or (existing.station_favicon if existing else None),
                source=source,
            )
        )

    async def _stored_source(
        self, device_id: str, source_id: str
    ) -> Optional[MediaServerSource]:
        """The media server stored under ``source_id`` for the device's account."""
        if not source_id.isdigit() or not self._device_repo or not self._source_repo:
            return None
        device = await self._device_repo.get_by_device_id(device_id)
        account = device.marge_account_uuid if device else None
        if not account:
            return None
        return await self._source_repo.get_by_id(account, int(source_id))

    async def delete_preset(self, device_id: str, slot: int) -> int:
        """Remove a preset the speaker deleted; returns the number of rows removed."""
        return await self._preset_repo.clear_preset(device_id, slot)

    async def add_source(
        self, account_id: str, server_id: str, display_name: str
    ) -> Optional[MediaServerSource]:
        """Store a media server the speaker registered; None if no device has the account."""
        if not self._device_repo or not self._source_repo:
            return None
        if not await self._device_repo.get_by_account_uuid(account_id):
            return None
        source = await self._source_repo.upsert(account_id, server_id, display_name)
        logger.info("[MARGE/SOURCE] Stored source %d", source.source_id)
        await self._push_sources_updated(account_id)
        return source

    async def remove_source(self, account_id: str, source_id: int) -> bool:
        """Remove a stored source; False (idempotent) if it did not exist."""
        if not self._source_repo or not await self._source_repo.delete(
            account_id, source_id
        ):
            return False
        logger.info("[MARGE/SOURCE] Removed source %d", source_id)
        await self._push_sources_updated(account_id)
        return True

    async def list_sources(self, account_id: str) -> list[MediaServerSource]:
        """List the account's stored media-server sources."""
        if not self._source_repo:
            return []
        return await self._source_repo.list_for_account(account_id)

    async def _push_sources_updated(self, account_id: str) -> None:
        """Tell the account's speaker to re-read its sources; never raises."""
        try:
            # shortcut: one device per account today, loop over all once accounts are shared
            device = (
                await self._device_repo.get_by_account_uuid(account_id)
                if self._device_repo
                else None
            )
            if not device:
                return
            client = self._client_factory(
                f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR - LAN HTTP only
            )
            try:
                await client.notify_sources_updated(device.device_id)
            finally:
                await client.close()
        except Exception as exc:  # noqa: BLE001 - a failed push must not fail the request
            logger.warning(
                "[MARGE/SOURCE] sourcesUpdated push failed: %s", type(exc).__name__
            )
