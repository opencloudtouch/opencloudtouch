"""Persistence of the media servers a speaker registered as STORED_MUSIC sources.

Migration range 500-599 is reserved for this table (400-499: Spotify plan).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Optional

from opencloudtouch.core.repository import BaseRepository

logger = logging.getLogger(__name__)

FIRST_SOURCE_ID = 20000000  # 8 digits like real Bose ids (unverified, hardware item H5)

_COLUMNS = (
    "source_id, device_id, server_id, display_name, removal_pending,"
    " received_provider_id, created_at, updated_at"
)


@dataclass(frozen=True)
class MediaServerSource:
    """One media server registered on one speaker (``<server_id>/0`` account)."""

    source_id: int
    device_id: str
    server_id: str
    display_name: str
    removal_pending: bool
    received_provider_id: int
    created_at: datetime
    updated_at: datetime

    @property
    def account(self) -> str:
        return f"{self.server_id}/0"


def _to_source(row: Any) -> MediaServerSource:
    return MediaServerSource(
        source_id=row[0],
        device_id=row[1],
        server_id=row[2],
        display_name=row[3],
        removal_pending=bool(row[4]),
        received_provider_id=row[5],
        created_at=datetime.fromisoformat(row[6]),
        updated_at=datetime.fromisoformat(row[7]),
    )


class MargeSourceRepository(BaseRepository):
    """SQLite store of ``media_server_sources``."""

    async def _create_schema(self) -> None:
        await self._apply_migration(
            version=500,
            description="Create media_server_sources table",
            sql="""
            CREATE TABLE IF NOT EXISTS media_server_sources (
                source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                server_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                removal_pending INTEGER NOT NULL DEFAULT 0,
                received_provider_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(device_id, server_id)
            )
            """,
        )
        # AUTOINCREMENT never reuses an id; seeding makes the first one 20000000
        await self._apply_migration(
            version=501,
            description="Seed media_server_sources id sequence",
            sql=f"""
            INSERT INTO sqlite_sequence (name, seq)
            SELECT 'media_server_sources', {FIRST_SOURCE_ID - 1}
            WHERE NOT EXISTS (
                SELECT 1 FROM sqlite_sequence WHERE name = 'media_server_sources'
            )
            """,
        )

    async def upsert(
        self,
        device_id: str,
        server_id: str,
        display_name: str,
        received_provider_id: int,
    ) -> MediaServerSource:
        """Create the row or refresh it; the database decides the id (idempotent)."""
        db = self._ensure_initialized()
        now = datetime.now(UTC).isoformat()
        cursor = await db.execute(
            f"""
            INSERT INTO media_server_sources (
                device_id, server_id, display_name, received_provider_id,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, server_id) DO UPDATE SET
                display_name = excluded.display_name,
                received_provider_id = excluded.received_provider_id,
                updated_at = excluded.updated_at
            RETURNING {_COLUMNS}
            """,  # nosec B608 - constant column list
            (device_id, server_id, display_name, received_provider_id, now, now),
        )
        row = await cursor.fetchone()
        await db.commit()
        assert row is not None
        return _to_source(row)

    async def _one(self, where: str, params: tuple) -> Optional[MediaServerSource]:
        db = self._ensure_initialized()
        cursor = await db.execute(
            f"SELECT {_COLUMNS} FROM media_server_sources WHERE {where}",  # nosec B608
            params,
        )
        row = await cursor.fetchone()
        return _to_source(row) if row else None

    async def get_by_id(self, source_id: int) -> Optional[MediaServerSource]:
        return await self._one("source_id = ?", (source_id,))

    async def get_by_server(
        self, device_id: str, server_id: str
    ) -> Optional[MediaServerSource]:
        return await self._one("device_id = ? AND server_id = ?", (device_id, server_id))

    async def list_active(self, device_id: str) -> list[MediaServerSource]:
        """Rows of a device that are not pending removal, oldest first."""
        db = self._ensure_initialized()
        cursor = await db.execute(
            f"SELECT {_COLUMNS} FROM media_server_sources"  # nosec B608
            " WHERE device_id = ? AND removal_pending = 0 ORDER BY source_id",
            (device_id,),
        )
        return [_to_source(row) for row in await cursor.fetchall()]

    async def count_for_device(self, device_id: str) -> int:
        db = self._ensure_initialized()
        cursor = await db.execute(
            "SELECT COUNT(*) FROM media_server_sources WHERE device_id = ?",
            (device_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def mark_removal_pending(self, device_id: str, source_id: int) -> None:
        """Flag a row of this device; an id of another device is never touched."""
        db = self._ensure_initialized()
        await db.execute(
            "UPDATE media_server_sources SET removal_pending = 1, updated_at = ?"
            " WHERE device_id = ? AND source_id = ?",
            (datetime.now(UTC).isoformat(), device_id, source_id),
        )
        await db.commit()

    async def delete_for_device(self, device_id: str) -> None:
        db = self._ensure_initialized()
        await db.execute(
            "DELETE FROM media_server_sources WHERE device_id = ?", (device_id,)
        )
        await db.commit()

    async def delete_all(self) -> None:
        db = self._ensure_initialized()
        await db.execute("DELETE FROM media_server_sources")
        await db.commit()
