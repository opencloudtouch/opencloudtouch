"""SQLite persistence for sleep timers (one row per device).

Migration range 425-449 is reserved for this domain (none needed yet: the table is
created with ``CREATE TABLE IF NOT EXISTS``). There is deliberately no foreign key
to ``devices``.
"""

from datetime import UTC, datetime

from opencloudtouch.core.repository import BaseRepository
from opencloudtouch.sleep_timer.models import END_ACTIONS, SleepTimer


def to_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso(text: str) -> float:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp()


class SleepTimerRepository(BaseRepository):
    async def _create_schema(self) -> None:
        actions = ", ".join(f"'{action}'" for action in END_ACTIONS)
        await self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS sleep_timers (
                device_id TEXT PRIMARY KEY,
                ends_at TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                fade_seconds INTEGER NOT NULL,
                end_action TEXT NOT NULL CHECK (end_action IN ({actions})),
                original_volume INTEGER,
                last_set_volume INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        await self._conn.commit()

    @staticmethod
    def _to_timer(row: tuple) -> SleepTimer:
        return SleepTimer(
            device_id=row[0],
            ends_at=from_iso(row[1]),
            duration_minutes=row[2],
            fade_seconds=row[3],
            end_action=row[4],
            original_volume=row[5],
            last_set_volume=row[6],
            created_at=from_iso(row[7]),
        )

    async def get(self, device_id: str) -> SleepTimer | None:
        cursor = await self._conn.execute(
            "SELECT device_id, ends_at, duration_minutes, fade_seconds, end_action, "
            "original_volume, last_set_volume, created_at FROM sleep_timers "
            "WHERE device_id = ?",
            (device_id,),
        )
        row = await cursor.fetchone()
        return self._to_timer(tuple(row)) if row else None

    async def list_all(self) -> list[SleepTimer]:
        cursor = await self._conn.execute(
            "SELECT device_id, ends_at, duration_minutes, fade_seconds, end_action, "
            "original_volume, last_set_volume, created_at FROM sleep_timers "
            "ORDER BY ends_at"
        )
        return [self._to_timer(tuple(row)) for row in await cursor.fetchall()]

    async def upsert(self, timer: SleepTimer) -> None:
        await self._conn.execute(
            """
            INSERT INTO sleep_timers (
                device_id, ends_at, duration_minutes, fade_seconds, end_action,
                original_volume, last_set_volume, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                ends_at = excluded.ends_at,
                duration_minutes = excluded.duration_minutes,
                fade_seconds = excluded.fade_seconds,
                end_action = excluded.end_action,
                original_volume = excluded.original_volume,
                last_set_volume = excluded.last_set_volume,
                created_at = excluded.created_at
            """,
            (
                timer.device_id,
                to_iso(timer.ends_at),
                timer.duration_minutes,
                timer.fade_seconds,
                timer.end_action,
                timer.original_volume,
                timer.last_set_volume,
                to_iso(timer.created_at),
            ),
        )
        await self._conn.commit()

    async def set_original_volume(self, device_id: str, volume: int | None) -> None:
        await self._conn.execute(
            "UPDATE sleep_timers SET original_volume = ? WHERE device_id = ?",
            (volume, device_id),
        )
        await self._conn.commit()

    async def set_last_set_volume(self, device_id: str, volume: int | None) -> None:
        await self._conn.execute(
            "UPDATE sleep_timers SET last_set_volume = ? WHERE device_id = ?",
            (volume, device_id),
        )
        await self._conn.commit()

    async def delete(self, device_id: str) -> None:
        await self._conn.execute(
            "DELETE FROM sleep_timers WHERE device_id = ?", (device_id,)
        )
        await self._conn.commit()
