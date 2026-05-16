"""Repository for preset persistence."""

import logging
from datetime import datetime
from typing import Any, List, Optional

from opencloudtouch.core.repository import BaseRepository
from opencloudtouch.presets.models import Preset

logger = logging.getLogger(__name__)


class PresetRepository(BaseRepository):
    """Repository for preset persistence using SQLite."""

    @staticmethod
    def _row_to_preset(row: tuple | Any) -> "Preset":
        """Map a database row tuple to a Preset model.

        Column order must match the SELECT column list used throughout this
        repository:  id, device_id, preset_number, station_uuid, station_name,
        station_url, station_homepage, station_favicon, source,
        created_at, updated_at.
        """
        return Preset(
            id=row[0],
            device_id=row[1],
            preset_number=row[2],
            station_uuid=row[3],
            station_name=row[4],
            station_url=row[5],
            station_homepage=row[6],
            station_favicon=row[7],
            source=row[8],
            created_at=datetime.fromisoformat(row[9]) if row[9] else None,
            updated_at=datetime.fromisoformat(row[10]) if row[10] else None,
        )

    async def _create_schema(self) -> None:
        """Create presets table, indexes and apply schema migrations."""
        # Base presets table (source column added via migration v1)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                preset_number INTEGER NOT NULL,
                station_uuid TEXT NOT NULL,
                station_name TEXT NOT NULL,
                station_url TEXT NOT NULL,
                station_homepage TEXT,
                station_favicon TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                UNIQUE(device_id, preset_number)
            )
            """)

        # Migrations (v1–v99 reserved for presets)
        await self._apply_migration(
            version=1,
            description="Add source column to presets",
            sql="ALTER TABLE presets ADD COLUMN source TEXT",
        )

        # Indexes
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_presets_device_id ON presets(device_id)
            """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_device_preset
            ON presets(device_id, preset_number)
            """)

        await self._conn.commit()

    async def set_preset(self, preset: Preset) -> Preset:
        """
        Insert or update a preset.

        Args:
            preset: Preset to save

        Returns:
            Preset with updated id

        Raises:
            RuntimeError: If database not initialized
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            INSERT INTO presets (
                device_id, preset_number, station_uuid, station_name, station_url,
                station_homepage, station_favicon, source, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, preset_number) DO UPDATE SET
                station_uuid = excluded.station_uuid,
                station_name = excluded.station_name,
                station_url = excluded.station_url,
                station_homepage = excluded.station_homepage,
                station_favicon = excluded.station_favicon,
                source = excluded.source,
                updated_at = excluded.updated_at
            RETURNING id
        """,
            (
                preset.device_id,
                preset.preset_number,
                preset.station_uuid,
                preset.station_name,
                preset.station_url,
                preset.station_homepage,
                preset.station_favicon,
                preset.source,
                preset.created_at,
                preset.updated_at,
            ),
        )

        row = await cursor.fetchone()
        preset.id = row[0] if row else None

        await db.commit()
        logger.debug(
            "Set preset %d for device %s: %s",
            preset.preset_number,
            preset.device_id,
            preset.station_name,
        )

        return preset

    async def get_preset(self, device_id: str, preset_number: int) -> Optional[Preset]:
        """
        Get a specific preset.

        Args:
            device_id: Device identifier
            preset_number: Preset slot (1-6)

        Returns:
            Preset if found, None otherwise

        Raises:
            RuntimeError: If database not initialized
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT id, device_id, preset_number, station_uuid, station_name,
                   station_url, station_homepage, station_favicon, source,
                   created_at, updated_at
            FROM presets
            WHERE device_id = ? AND preset_number = ?
        """,
            (device_id, preset_number),
        )

        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_preset(row)

    async def get_all_presets(self, device_id: str) -> List[Preset]:
        """
        Get all presets for a device.

        Args:
            device_id: Device identifier

        Returns:
            List of presets, ordered by preset_number

        Raises:
            RuntimeError: If database not initialized
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT id, device_id, preset_number, station_uuid, station_name,
                   station_url, station_homepage, station_favicon, source,
                   created_at, updated_at
            FROM presets
            WHERE device_id = ?
            ORDER BY preset_number ASC
        """,
            (device_id,),
        )

        rows = await cursor.fetchall()

        presets = [self._row_to_preset(row) for row in rows]

        return presets

    async def clear_preset(self, device_id: str, preset_number: int) -> int:
        """
        Clear a specific preset.

        Args:
            device_id: Device identifier
            preset_number: Preset slot (1-6)

        Returns:
            Number of deleted rows (0 or 1)

        Raises:
            RuntimeError: If database not initialized
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            "DELETE FROM presets WHERE device_id = ? AND preset_number = ?",
            (device_id, preset_number),
        )

        await db.commit()

        deleted_count = cursor.rowcount
        if deleted_count > 0:
            logger.debug("Cleared preset %d for device %s", preset_number, device_id)

        return deleted_count

    async def clear_all_presets(self, device_id: str) -> int:
        """
        Clear all presets for a device.

        Args:
            device_id: Device identifier

        Returns:
            Number of deleted rows

        Raises:
            RuntimeError: If database not initialized
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            "DELETE FROM presets WHERE device_id = ?",
            (device_id,),
        )

        await db.commit()

        deleted_count = cursor.rowcount
        if deleted_count > 0:
            logger.debug(
                f"Cleared all presets ({deleted_count}) for device {device_id}"
            )

        return deleted_count
