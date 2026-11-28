"""Marge STORED_MUSIC sources registered through OCT, keyed by account and server."""

from dataclasses import dataclass
from datetime import UTC, datetime

import aiosqlite

from opencloudtouch.core.repository import BaseRepository

FIRST_SOURCE_ID = 20000000


@dataclass(frozen=True)
class MediaServerSource:
    """A media server registered as a source of one Marge account."""

    source_id: int
    account_id: str
    server_id: str
    display_name: str
    created_at: datetime
    updated_at: datetime

    @property
    def account(self) -> str:
        """Return the speaker's STORED_MUSIC account token."""
        return f"{self.server_id}/0"


def _server_id(server_id: str) -> str:
    # Case is kept exactly as the speaker reports it (decision 48).
    return server_id.removeprefix("uuid:")


def _to_source(row: aiosqlite.Row) -> MediaServerSource:
    return MediaServerSource(
        source_id=row["source_id"],
        account_id=row["account_id"],
        server_id=row["server_id"],
        display_name=row["display_name"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class MargeSourceRepository(BaseRepository):
    """Persist source identities per Marge account."""

    async def _create_schema(self) -> None:
        self._conn.row_factory = aiosqlite.Row
        # Migrations 500-599 are reserved for Marge sources.
        await self._apply_migration(
            version=500,
            description="Create media_server_sources table",
            sql="""
                CREATE TABLE IF NOT EXISTS media_server_sources (
                    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    server_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(account_id, server_id)
                )
            """,
        )
        await self._apply_migration(
            version=501,
            description="Seed media_server_sources id sequence",
            # Seed FIRST_SOURCE_ID - 1; SQLite increments before allocating.
            sql="""
                INSERT INTO sqlite_sequence (name, seq)
                SELECT 'media_server_sources', 19999999
                WHERE NOT EXISTS (
                    SELECT 1 FROM sqlite_sequence
                    WHERE name = 'media_server_sources'
                )
            """,
        )

    async def upsert(
        self, account_id: str, server_id: str, display_name: str
    ) -> MediaServerSource:
        """Create or update a source while keeping its id."""
        db = self._conn
        now = datetime.now(UTC).isoformat()
        rows = await db.execute_fetchall(
            """
                INSERT INTO media_server_sources (
                    account_id, server_id, display_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(account_id, server_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    updated_at = excluded.updated_at
                RETURNING *
            """,
            (account_id, _server_id(server_id), display_name, now, now),
        )
        await db.commit()
        return _to_source(next(iter(rows)))

    async def _one(self, where: str, params: tuple) -> MediaServerSource | None:
        async with self._conn.execute(
            f"SELECT * FROM media_server_sources WHERE {where}",  # nosec B608
            params,
        ) as cursor:
            row = await cursor.fetchone()
        return _to_source(row) if row else None

    async def get(self, account_id: str, server_id: str) -> MediaServerSource | None:
        """Read a source by account and server."""
        return await self._one(
            "account_id = ? AND server_id = ?", (account_id, _server_id(server_id))
        )

    async def get_by_id(
        self, account_id: str, source_id: int
    ) -> MediaServerSource | None:
        """Read a source by account and source id."""
        return await self._one(
            "account_id = ? AND source_id = ?", (account_id, source_id)
        )

    async def list_for_account(self, account_id: str) -> list[MediaServerSource]:
        """List an account's sources in allocation order."""
        async with self._conn.execute(
            "SELECT * FROM media_server_sources WHERE account_id = ? "
            "ORDER BY source_id",
            (account_id,),
        ) as cursor:
            return [_to_source(row) for row in await cursor.fetchall()]

    async def delete(self, account_id: str, source_id: int) -> bool:
        """Delete a source, returning whether a row existed."""
        db = self._conn
        async with db.execute(
            "DELETE FROM media_server_sources WHERE account_id = ? AND source_id = ?",
            (account_id, source_id),
        ) as cursor:
            deleted = cursor.rowcount > 0
        await db.commit()
        return deleted
