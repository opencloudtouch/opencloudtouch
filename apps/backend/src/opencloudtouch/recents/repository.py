"""Repository for recently played items persistence."""

import logging
from datetime import datetime
from typing import Any, Optional

from opencloudtouch.core.repository import BaseRepository
from opencloudtouch.recents.models import RecentPlay

logger = logging.getLogger(__name__)

# Maximum number of recent items per device
MAX_RECENTS_PER_DEVICE = 20


class RecentsRepository(BaseRepository):
    """Repository for recently played items using SQLite."""

    @staticmethod
    def _row_to_recent(row: tuple | Any) -> RecentPlay:
        """Map a database row to a RecentPlay model.

        Column order: id, device_id, source, location, name, image_url, played_at.
        """
        return RecentPlay(
            id=row[0],
            device_id=row[1],
            source=row[2],
            location=row[3],
            name=row[4],
            image_url=row[5],
            played_at=datetime.fromisoformat(row[6]) if row[6] else None,
        )

    async def _create_schema(self) -> None:
        """Create recents table and indexes."""
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS recents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                source TEXT NOT NULL,
                location TEXT NOT NULL,
                name TEXT NOT NULL,
                image_url TEXT,
                played_at TIMESTAMP NOT NULL
            )
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_recents_device_id
            ON recents(device_id)
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_recents_device_played
            ON recents(device_id, played_at DESC)
        """)

        await self._conn.commit()

    async def add_recent(self, recent: RecentPlay) -> RecentPlay:
        """Add a recently played item.

        If the same location already exists for the device, updates the
        played_at timestamp instead of creating a duplicate.
        Enforces MAX_RECENTS_PER_DEVICE per device by pruning oldest entries.

        Args:
            recent: RecentPlay to save

        Returns:
            RecentPlay with updated id and played_at
        """
        db = self._ensure_initialized()

        # Upsert: if same device+location exists, update timestamp
        cursor = await db.execute(
            """
            SELECT id FROM recents
            WHERE device_id = ? AND location = ?
            """,
            (recent.device_id, recent.location),
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute(
                """
                UPDATE recents
                SET name = ?, source = ?, image_url = ?, played_at = ?
                WHERE id = ?
                """,
                (
                    recent.name,
                    recent.source,
                    recent.image_url,
                    recent.played_at,
                    existing[0],
                ),
            )
            recent.id = existing[0]
        else:
            cursor = await db.execute(
                """
                INSERT INTO recents (device_id, source, location, name, image_url, played_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    recent.device_id,
                    recent.source,
                    recent.location,
                    recent.name,
                    recent.image_url,
                    recent.played_at,
                ),
            )
            recent.id = cursor.lastrowid

        # Prune oldest entries beyond limit
        await db.execute(
            """
            DELETE FROM recents
            WHERE device_id = ? AND id NOT IN (
                SELECT id FROM recents
                WHERE device_id = ?
                ORDER BY played_at DESC
                LIMIT ?
            )
            """,
            (recent.device_id, recent.device_id, MAX_RECENTS_PER_DEVICE),
        )

        await db.commit()
        logger.debug("Added recent for device %s: %s", recent.device_id, recent.name)

        return recent

    async def get_recents(
        self, device_id: str, limit: Optional[int] = None
    ) -> list[RecentPlay]:
        """Get recently played items for a device.

        Args:
            device_id: Device MAC address
            limit: Maximum items to return (default: MAX_RECENTS_PER_DEVICE)

        Returns:
            List of RecentPlay items, newest first
        """
        db = self._ensure_initialized()
        effective_limit = limit or MAX_RECENTS_PER_DEVICE

        cursor = await db.execute(
            """
            SELECT id, device_id, source, location, name, image_url, played_at
            FROM recents
            WHERE device_id = ?
            ORDER BY played_at DESC
            LIMIT ?
            """,
            (device_id, effective_limit),
        )

        rows = await cursor.fetchall()
        return [self._row_to_recent(row) for row in rows]

    async def clear_recents(self, device_id: str) -> int:
        """Clear all recent items for a device.

        Args:
            device_id: Device MAC address

        Returns:
            Number of deleted rows
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            "DELETE FROM recents WHERE device_id = ?",
            (device_id,),
        )
        await db.commit()

        deleted = cursor.rowcount
        if deleted > 0:
            logger.debug("Cleared %d recents for device %s", deleted, device_id)
        return deleted
