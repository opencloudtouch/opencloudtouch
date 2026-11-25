"""Migration version and last error per speaker."""

from datetime import UTC, datetime

from opencloudtouch.core.repository import BaseRepository


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SpeakerMigrationRepository(BaseRepository):
    """Persist each speaker's migration version (no row = version 0)."""

    async def _create_schema(self) -> None:
        # Migrations 600-699 are reserved for speaker migrations.
        await self._apply_migration(
            version=600,
            description="Create speaker_migrations table",
            sql="""
                CREATE TABLE IF NOT EXISTS speaker_migrations (
                    device_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                )
            """,
        )

    async def get(self, device_id: str) -> tuple[int, str | None]:
        """Return (version, last_error); a speaker without a row is on version 0."""
        cursor = await self._conn.execute(
            "SELECT version, last_error FROM speaker_migrations WHERE device_id = ?",
            (device_id,),
        )
        row = await cursor.fetchone()
        return (row[0], row[1]) if row else (0, None)

    async def set_version(self, device_id: str, version: int) -> None:
        """Store the version reached and clear the last error."""
        await self._conn.execute(
            """
            INSERT INTO speaker_migrations (device_id, version, last_error, updated_at)
            VALUES (?, ?, NULL, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                version = excluded.version,
                last_error = NULL,
                updated_at = excluded.updated_at
            """,
            (device_id, version, _now()),
        )
        await self._conn.commit()

    async def set_error(self, device_id: str, reason: str) -> None:
        """Record why a step failed; the stored version stays unchanged."""
        await self._conn.execute(
            """
            INSERT INTO speaker_migrations (device_id, version, last_error, updated_at)
            VALUES (?, 0, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (device_id, reason, _now()),
        )
        await self._conn.commit()
