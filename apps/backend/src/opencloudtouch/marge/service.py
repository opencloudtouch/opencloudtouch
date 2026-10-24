"""Marge account sync service.

Orchestrates preset and recents data for Bose streaming.bose.com
account sync protocol. Keeps route handlers thin.
"""

import asyncio
import logging
import time
from typing import Optional

from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.recents.models import RecentPlay
from opencloudtouch.recents.repository import RecentsRepository

logger = logging.getLogger(__name__)


def _uuid_refresh_now() -> float:
    """Return monotonic time for UUID refresh rate limiting."""
    return time.monotonic()


class MargeService:
    """Orchestrates account data assembly for Bose device sync."""

    def __init__(
        self,
        preset_repo: PresetRepository,
        recents_repo: RecentsRepository,
        device_repo: Optional[DeviceRepository] = None,
    ) -> None:
        self._preset_repo = preset_repo
        self._recents_repo = recents_repo
        self._device_repo = device_repo
        self._uuid_refresh_lock = asyncio.Lock()
        self._uuid_refresh_times: list[float] = []

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

        recovered = await self._recover_unknown_account(account_id)
        if recovered:
            return recovered

        logger.warning(  # NOSONAR
            "[MARGE] No device found for account UUID %s", account_id
        )
        return None

    async def _recover_unknown_account(self, account_id: str) -> Optional[str]:
        """Read known speakers on unknown UUID, with one scan at most per 5s
        and three scans in a sliding minute. Never change speaker UUIDs.
        """
        from opencloudtouch.setup.account_pairing_service import (
            check_marge_account_uuid,
        )

        if not self._device_repo or not account_id.isdigit() or len(account_id) < 7:
            return None
        async with self._uuid_refresh_lock:
            # Another request may already have reconciled this UUID.
            resolved = await self._device_repo.get_by_account_uuid(account_id)
            if resolved:
                return resolved.device_id
            now = _uuid_refresh_now()
            self._uuid_refresh_times = [
                t for t in self._uuid_refresh_times if now - t < 60
            ]
            if (
                self._uuid_refresh_times and now - self._uuid_refresh_times[-1] < 5
            ) or len(self._uuid_refresh_times) >= 3:
                return None
            self._uuid_refresh_times.append(now)
            for device in await self._device_repo.get_all():
                if not device.ip:
                    continue
                try:
                    uuid = await asyncio.wait_for(
                        check_marge_account_uuid(device.ip, raise_on_error=True),
                        timeout=3,
                    )
                except Exception:
                    logger.debug(
                        "[MARGE] UUID refresh failed for %s",
                        device.device_id,
                        exc_info=True,
                    )
                    continue
                if uuid != account_id:
                    continue
                owner = await self._device_repo.get_by_account_uuid(uuid)
                if owner is not None and owner.device_id != device.device_id:
                    logger.warning(
                        "[MARGE] UUID collision on refresh: %s and %s",
                        owner.device_id,
                        device.device_id,
                    )
                    return None
                try:
                    await self._device_repo.update_marge_account_uuid(
                        device.device_id, uuid
                    )
                except ValueError:
                    logger.warning(
                        "[MARGE] UUID %s could not be reconciled for %s",
                        uuid,
                        device.device_id,
                    )
                    return None
                logger.info("[MARGE] Reconciled UUID for %s", device.device_id)
                return device.device_id
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

    async def get_recents(self, device_id: str) -> list[RecentPlay]:
        """Get recently played items for a device."""
        return await self._recents_repo.get_recents(device_id)
