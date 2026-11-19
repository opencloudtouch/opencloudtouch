"""Stereo pair service: group handling for the Marge endpoints and OCT lifecycle."""

import logging
import time
from typing import Callable, Dict, Optional

from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.stereo_pairs.repository import (
    DeviceAlreadyPairedError,
    StereoPair,
    StereoPairRepository,
)
from opencloudtouch.stereo_pairs.xml import (
    GroupRequest,
    InvalidGroupError,
    validate_create_request,
)

logger = logging.getLogger(__name__)

INTENT_TTL_SECONDS = 120.0


class UnknownDeviceError(LookupError):
    """Raised when a Marge request names a device OCT does not know."""


class StereoPairService:
    """Keeps the stereo pair records and answers the speakers' Marge calls."""

    def __init__(
        self,
        repo: StereoPairRepository,
        device_repo: DeviceRepository,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._repo = repo
        self._device_repo = device_repo
        self._clock = clock
        # master device id -> expiry; set by OCT right before it calls addGroup
        self._intents: Dict[str, float] = {}

    # ---- create intents (OCT-initiated pairing) ----

    def expect_create(self, master_device_id: str) -> None:
        """Mark that OCT is about to ask this master to create a group."""
        self._intents[master_device_id] = self._clock() + INTENT_TTL_SECONDS

    def clear_intent(self, master_device_id: str) -> None:
        self._intents.pop(master_device_id, None)

    def _consume_intent(self, master_device_id: str) -> bool:
        expiry = self._intents.pop(master_device_id, None)
        return expiry is not None and expiry > self._clock()

    # ---- Marge side (called by the speakers) ----

    async def marge_create(self, request: GroupRequest) -> StereoPair:
        """Create (or idempotently return) the group a speaker asks Marge for.

        Raises InvalidGroupError, DeviceAlreadyPairedError.
        """
        validate_create_request(request)
        left, right = request.left_device_id, request.right_device_id

        existing = await self._repo.get_by_device(left)
        if existing is not None:
            same = (
                existing.left_device_id == left
                and existing.right_device_id == right
                and existing.master_device_id == request.master_device_id
            )
            if same:
                logger.info("[STEREO] Repeated group create for pair %d", existing.id)
                return existing
            raise DeviceAlreadyPairedError(left)

        planned_by_oct = self._consume_intent(request.master_device_id)
        name = request.name or f"{left} + {right}"
        pair = await self._repo.create_pair(
            name,
            request.master_device_id,
            left,
            right,
            status="pending" if planned_by_oct else "active",
            source="oct" if planned_by_oct else "device",
        )
        logger.info(
            "[STEREO] Group %d created via Marge (source=%s)", pair.id, pair.source
        )
        return pair

    async def get_for_device(self, device_id: str) -> Optional[StereoPair]:
        """Group of a device, or None. Raises UnknownDeviceError for unknown ids."""
        if await self._device_repo.get_by_device_id(device_id) is None:
            raise UnknownDeviceError(device_id)
        return await self._repo.get_by_device(device_id)

    async def marge_rename(self, group_id: int, name: str) -> Optional[StereoPair]:
        if not name:
            raise InvalidGroupError("Group name must not be empty")
        if await self._repo.get(group_id) is None:
            return None
        await self._repo.rename(group_id, name)
        return await self._repo.get(group_id)

    async def marge_dissolve(self, group_id: int) -> None:
        """Dissolve a group. Idempotent: unknown ids are ignored."""
        await self._repo.dissolve(group_id)
        logger.info("[STEREO] Group %d dissolved via Marge", group_id)
