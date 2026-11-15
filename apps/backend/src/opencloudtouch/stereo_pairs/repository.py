"""Stereo pair repository: persistent LEFT/RIGHT pairs of two speakers."""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import AsyncIterator, List, Optional

from opencloudtouch.core.repository import BaseRepository

logger = logging.getLogger(__name__)


class DeviceAlreadyPairedError(ValueError):
    """Raised when a device already belongs to an active stereo pair."""

    def __init__(self, device_id: str):
        super().__init__(f"Device {device_id} already belongs to a stereo pair")
        self.device_id = device_id


@dataclass
class StereoPair:
    """A persistent stereo pair. ``id`` is the group id handed to the speakers."""

    id: int
    name: str
    master_device_id: str
    left_device_id: str
    right_device_id: str
    created_at: datetime
    status: str = "active"  # "pending" | "active"
    source: str = "oct"  # "oct" | "device" (created outside OCT, imported)


_COLUMNS = (
    "id, name, master_device_id, left_device_id, right_device_id, created_at, "
    "status, source"
)


def _row_to_pair(row) -> StereoPair:
    created = row[5]
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    return StereoPair(row[0], row[1], row[2], row[3], row[4], created, row[6], row[7])


class StereoPairRepository(BaseRepository):
    """Persistence for stereo pairs (soft delete via ``dissolved_at``)."""

    def __init__(self, db_path):
        super().__init__(db_path)
        self._write_lock = asyncio.Lock()

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        db = self._ensure_initialized()
        async with self._write_lock:
            try:
                await db.execute("BEGIN IMMEDIATE")
                yield
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def _create_schema(self) -> None:
        # Migrations v300-v399 reserved for stereo pairs
        await self._apply_migration(
            version=300,
            description="Create stereo_pairs table",
            sql="""
                CREATE TABLE IF NOT EXISTS stereo_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    master_device_id TEXT NOT NULL,
                    left_device_id TEXT NOT NULL,
                    right_device_id TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    dissolved_at TIMESTAMP NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    source TEXT NOT NULL DEFAULT 'oct'
                )
            """,
        )
        await self._apply_migration(
            version=301,
            description="Index active stereo pair members",
            sql="""
                CREATE INDEX IF NOT EXISTS idx_stereo_pairs_active
                ON stereo_pairs(left_device_id, right_device_id)
                WHERE dissolved_at IS NULL
            """,
        )
        await self._conn.commit()

    async def _find_active(self, device_id: str) -> Optional[StereoPair]:
        db = self._ensure_initialized()
        cursor = await db.execute(
            f"SELECT {_COLUMNS} FROM stereo_pairs "  # nosec B608 - _COLUMNS is a module constant, all values are bound parameters
            "WHERE dissolved_at IS NULL AND (left_device_id = ? OR right_device_id = ?)",
            (device_id, device_id),
        )
        row = await cursor.fetchone()
        return _row_to_pair(row) if row else None

    async def create_pair(
        self,
        name: str,
        master_device_id: str,
        left_id: str,
        right_id: str,
        *,
        status: str = "active",
        source: str = "oct",
    ) -> StereoPair:
        """Create a pair; raises DeviceAlreadyPairedError if a member is taken."""
        db = self._ensure_initialized()
        async with self._transaction():
            for device_id in (left_id, right_id):
                if await self._find_active(device_id):
                    raise DeviceAlreadyPairedError(device_id)
            now = datetime.now(UTC)
            cursor = await db.execute(
                "INSERT INTO stereo_pairs "
                "(name, master_device_id, left_device_id, right_device_id, created_at, "
                "status, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, master_device_id, left_id, right_id, now, status, source),
            )
            pair_id = cursor.lastrowid
        if pair_id is None:
            raise RuntimeError("Stereo pair has no ID after INSERT")
        logger.info("Created stereo pair %d (%s / %s)", pair_id, left_id, right_id)
        return StereoPair(
            pair_id, name, master_device_id, left_id, right_id, now, status, source
        )

    async def get_by_device(self, device_id: str) -> Optional[StereoPair]:
        return await self._find_active(device_id)

    async def get(self, pair_id: int) -> Optional[StereoPair]:
        db = self._ensure_initialized()
        cursor = await db.execute(
            f"SELECT {_COLUMNS} FROM stereo_pairs WHERE id = ? AND dissolved_at IS NULL",  # nosec B608 - _COLUMNS is a module constant, all values are bound parameters
            (pair_id,),
        )
        row = await cursor.fetchone()
        return _row_to_pair(row) if row else None

    async def list_active(self) -> List[StereoPair]:
        db = self._ensure_initialized()
        cursor = await db.execute(
            f"SELECT {_COLUMNS} FROM stereo_pairs WHERE dissolved_at IS NULL ORDER BY id"  # nosec B608 - _COLUMNS is a module constant, all values are bound parameters
        )
        return [_row_to_pair(row) for row in await cursor.fetchall()]

    async def rename(self, pair_id: int, name: str) -> None:
        db = self._ensure_initialized()
        async with self._transaction():
            await db.execute(
                "UPDATE stereo_pairs SET name = ? WHERE id = ? AND dissolved_at IS NULL",
                (name, pair_id),
            )

    async def dissolve(self, pair_id: int) -> None:
        """Mark a pair dissolved. Idempotent; unknown ids are ignored."""
        db = self._ensure_initialized()
        async with self._transaction():
            await db.execute(
                "UPDATE stereo_pairs SET dissolved_at = ? "
                "WHERE id = ? AND dissolved_at IS NULL",
                (datetime.now(UTC), pair_id),
            )

    async def set_status(self, pair_id: int, status: str) -> None:
        db = self._ensure_initialized()
        async with self._transaction():
            await db.execute(
                "UPDATE stereo_pairs SET status = ? WHERE id = ? AND dissolved_at IS NULL",
                (status, pair_id),
            )

    async def delete(self, pair_id: int) -> None:
        """Remove a row entirely (used to discard a pending pair after rollback)."""
        db = self._ensure_initialized()
        async with self._transaction():
            await db.execute("DELETE FROM stereo_pairs WHERE id = ?", (pair_id,))
