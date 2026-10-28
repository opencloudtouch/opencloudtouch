"""SQLite persistence for stream recovery (config row + capped event log).

Migration range 600-624 is reserved for this domain (none needed yet: the tables
are created with ``CREATE TABLE IF NOT EXISTS``).
"""

from datetime import UTC, datetime

from opencloudtouch.core.repository import BaseRepository
from opencloudtouch.streamrecovery.models import (
    OUTCOMES,
    StreamRecoveryConfig,
    StreamRecoveryEvent,
)

MAX_EVENTS = 100


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class StreamRecoveryRepository(BaseRepository):
    """Stores the single config row and the newest ``MAX_EVENTS`` events."""

    async def _create_schema(self) -> None:
        outcomes = ", ".join(f"'{outcome}'" for outcome in OUTCOMES)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stream_recovery_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                min_play_seconds INTEGER NOT NULL DEFAULT 600,
                max_attempts_per_hour INTEGER NOT NULL DEFAULT 3,
                updated_at TEXT NOT NULL
            )
        """)
        await self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS stream_recovery_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                device_id TEXT NOT NULL,
                preset_number INTEGER,
                station_name TEXT,
                play_seconds INTEGER,
                outcome TEXT NOT NULL CHECK (outcome IN ({outcomes})),
                attempts INTEGER NOT NULL DEFAULT 0,
                error_code TEXT
            )
        """)
        await self._conn.commit()

    async def get_config(self) -> StreamRecoveryConfig:
        cursor = await self._conn.execute(
            "SELECT enabled, min_play_seconds, max_attempts_per_hour, updated_at "
            "FROM stream_recovery_config WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return StreamRecoveryConfig()
        return StreamRecoveryConfig(
            enabled=bool(row[0]),
            min_play_seconds=row[1],
            max_attempts_per_hour=row[2],
            updated_at=row[3],
        )

    async def set_config(
        self, enabled: bool, min_play_seconds: int, max_attempts_per_hour: int
    ) -> StreamRecoveryConfig:
        updated_at = _utc_now()
        await self._conn.execute(
            """
            INSERT INTO stream_recovery_config
                (id, enabled, min_play_seconds, max_attempts_per_hour, updated_at)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                enabled = excluded.enabled,
                min_play_seconds = excluded.min_play_seconds,
                max_attempts_per_hour = excluded.max_attempts_per_hour,
                updated_at = excluded.updated_at
            """,
            (int(enabled), min_play_seconds, max_attempts_per_hour, updated_at),
        )
        await self._conn.commit()
        return StreamRecoveryConfig(
            enabled=enabled,
            min_play_seconds=min_play_seconds,
            max_attempts_per_hour=max_attempts_per_hour,
            updated_at=updated_at,
        )

    async def add_event(self, event: StreamRecoveryEvent) -> None:
        """Insert *event* and trim the log to ``MAX_EVENTS`` in one transaction."""
        try:
            await self._conn.execute(
                """
                INSERT INTO stream_recovery_events
                    (occurred_at, device_id, preset_number, station_name,
                     play_seconds, outcome, attempts, error_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.occurred_at,
                    event.device_id,
                    event.preset_number,
                    event.station_name,
                    event.play_seconds,
                    event.outcome,
                    event.attempts,
                    event.error_code,
                ),
            )
            await self._conn.execute(
                """
                DELETE FROM stream_recovery_events WHERE id NOT IN (
                    SELECT id FROM stream_recovery_events ORDER BY id DESC LIMIT ?
                )
                """,
                (MAX_EVENTS,),
            )
            await self._conn.commit()
        except Exception:
            await self._conn.rollback()
            raise

    async def list_events(self, limit: int = 20) -> list[StreamRecoveryEvent]:
        """Newest first."""
        cursor = await self._conn.execute(
            """
            SELECT id, occurred_at, device_id, preset_number, station_name,
                   play_seconds, outcome, attempts, error_code
            FROM stream_recovery_events ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )
        return [
            StreamRecoveryEvent(
                id=row[0],
                occurred_at=row[1],
                device_id=row[2],
                preset_number=row[3],
                station_name=row[4],
                play_seconds=row[5],
                outcome=row[6],
                attempts=row[7],
                error_code=row[8],
            )
            for row in await cursor.fetchall()
        ]
