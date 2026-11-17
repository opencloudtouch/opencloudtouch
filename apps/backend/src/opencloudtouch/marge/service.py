"""Marge account sync service.

Orchestrates preset and recents data for Bose streaming.bose.com
account sync protocol. Keeps route handlers thin.
"""

import base64
import json
import logging
from copy import copy
from typing import Optional
from urllib.parse import parse_qs, urlparse

from opencloudtouch.core.dlna_reference import (
    DlnaReference,
    from_station_url,
    parse_orion_data,
    strip_native_location,
    to_station_url,
)
from opencloudtouch.core.dlna_reference import station_uuid as dlna_station_uuid
from opencloudtouch.core.source_types import source_type_for_streaming_id
from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.marge.source_repository import (
    MargeSourceRepository,
    MediaServerSource,
)
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.recents.models import RecentPlay
from opencloudtouch.recents.repository import RecentsRepository

logger = logging.getLogger(__name__)

_NATIVE_TYPES = ("dir", "track")


class UnknownAccountError(Exception):
    """The account id does not resolve to a known device."""


class AccountMismatchError(Exception):
    """The account of a speaker call does not belong to the device it names."""


def _station_from_location(source: str, location: str, name: str) -> tuple[str, str]:
    """Stream URL and artwork behind a preset location the speaker reports.

    OCT hands out Orion adapter locations (``...station?data=<base64 json>``) for
    its own stations; storing that URL again would wrap it twice, so unwrap it.
    """
    if source != "TUNEIN":
        data = parse_qs(urlparse(location).query).get("data")
        if data:
            dlna = parse_orion_data(data[0])
            if dlna is not None:
                return to_station_url(dlna[0]), ""
            try:
                decoded = json.loads(base64.urlsafe_b64decode(data[0]))
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
    ) -> None:
        self._preset_repo = preset_repo
        self._recents_repo = recents_repo
        self._device_repo = device_repo
        self._source_repo = source_repo

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
                "[MARGE] Resolved account %s -> device %s",
                account_id,
                device.device_id,
            )
            logger.debug("[MARGE] Resolved device name: %s", device.name)
            return device.device_id

        # Fallback: account_id might be the device_id itself (MAC address)
        device = await self._device_repo.get_by_device_id(account_id)
        if device:
            logger.info(  # NOSONAR
                "[MARGE] Fallback: account_id %s is device_id", account_id
            )
            logger.debug("[MARGE] Fallback device name: %s", device.name)
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

    async def get_active_sources(self, device_id: str) -> list[MediaServerSource]:
        """Media servers OpenCloudTouch lists as sources for a device."""
        if not self._source_repo:
            return []
        return await self._source_repo.list_active(device_id)

    async def is_known_device(self, account_id: str, device_id: str) -> bool:
        """True when the account resolves to exactly this device."""
        resolved = await self.resolve_device_id_for_account(account_id)
        return resolved is not None and resolved.casefold() == device_id.casefold()

    async def _registered_source(
        self, device_id: str, account_id: str, source_id: str
    ) -> Optional[MediaServerSource]:
        """Row behind a numeric source id; the account must resolve to its device."""
        if not (self._source_repo and source_id.isdigit()):
            return None
        row = await self._source_repo.get_by_id(int(source_id))
        if row is None:
            return None
        if (
            row.device_id != device_id
            or await self.resolve_device_id_for_account(account_id) != device_id
        ):
            raise AccountMismatchError
        return row

    async def store_preset(
        self,
        device_id: str,
        slot: int,
        source_id: str,
        name: str,
        location: str,
        content_item_type: str = "",
        account_id: str = "",
    ) -> Preset:
        """Store a preset the speaker wrote (upsert; keeps uuid and homepage of the slot)."""
        source = source_type_for_streaming_id(source_id) or source_id
        row = None
        if source == source_id:
            row = await self._registered_source(device_id, account_id, source_id)
        existing = await self._preset_repo.get_preset(device_id, slot)
        if row is None and source_id.isdigit() and existing:
            # The speaker calls back only a numeric id it may have renumbered: the
            # slot keeps its DLNA row when the object is the same.
            ref = from_station_url(existing.station_url)
            kept_type = existing.native_type or "dir"
            if (
                existing.source == "DLNA"
                and ref
                and ref.object_id == strip_native_location(location, kept_type)
            ):
                kept = copy(existing)
                kept.station_name = name
                return await self._preset_repo.set_preset(kept)
        native_type = None
        if row:
            native_type = (
                content_item_type if content_item_type in _NATIVE_TYPES else "dir"
            )
            native_ref = DlnaReference(
                row.server_id, strip_native_location(location, native_type)
            )
            dlna_ref: Optional[DlnaReference] = native_ref
            station_url, art = to_station_url(native_ref), ""
        else:
            station_url, art = _station_from_location(source, location, name)
            dlna_ref = from_station_url(station_url)
        if dlna_ref is not None:
            source = "DLNA"
        return await self._preset_repo.set_preset(
            Preset(
                device_id=device_id,
                preset_number=slot,
                station_uuid=(
                    dlna_station_uuid(dlna_ref)
                    if dlna_ref
                    else existing.station_uuid if existing else f"marge_{slot}"
                ),
                station_name=name,
                station_url=station_url,
                station_homepage=existing.station_homepage if existing else None,
                station_favicon=art or (existing.station_favicon if existing else None),
                source=source,
                native_type=native_type,
            )
        )

    async def delete_preset(self, device_id: str, slot: int) -> int:
        """Remove a preset the speaker deleted; returns the number of rows removed."""
        return await self._preset_repo.clear_preset(device_id, slot)
