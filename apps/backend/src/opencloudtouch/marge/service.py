"""Marge account sync service.

Orchestrates preset and recents data for Bose streaming.bose.com
account sync protocol. Keeps route handlers thin.
"""

import logging
from typing import Optional

from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.recents.models import RecentPlay
from opencloudtouch.recents.repository import RecentsRepository

logger = logging.getLogger(__name__)


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

    async def get_recents(self, device_id: str) -> list[RecentPlay]:
        """Get recently played items for a device."""
        return await self._recents_repo.get_recents(device_id)
