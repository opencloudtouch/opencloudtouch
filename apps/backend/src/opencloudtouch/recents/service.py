"""Service layer for recently played items."""

import logging

from opencloudtouch.recents.models import RecentPlay
from opencloudtouch.recents.repository import RecentsRepository

logger = logging.getLogger(__name__)


class RecentsService:
    """Service for managing recently played items."""

    def __init__(self, repository: RecentsRepository) -> None:
        self._repo = repository

    async def get_recents(self, device_id: str) -> list[RecentPlay]:
        """Get recently played items for a device."""
        return await self._repo.get_recents(device_id)

    async def add_recent(self, recent: RecentPlay) -> RecentPlay:
        """Add a recently played item (upserts if same location exists)."""
        return await self._repo.add_recent(recent)
