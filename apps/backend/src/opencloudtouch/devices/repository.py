"""
Database models and repository for device management
Uses aiosqlite for async SQLite operations
"""

import logging
from datetime import UTC, datetime
from typing import Any, List, Optional

import aiosqlite

from opencloudtouch.core.repository import BaseRepository

logger = logging.getLogger(__name__)


class Device:
    """Device model."""

    def __init__(
        self,
        device_id: str,
        ip: str,
        name: str,
        model: str,
        mac_address: str,
        firmware_version: str,
        schema_version: Optional[str] = None,
        last_seen: Optional[datetime] = None,
        id: Optional[int] = None,
    ):
        self.id = id
        self.device_id = device_id
        self.ip = ip
        self.name = name
        self.model = model
        self.mac_address = mac_address
        self.firmware_version = firmware_version
        self.schema_version = schema_version or self._extract_schema_version(
            firmware_version
        )
        self.last_seen = last_seen or datetime.now(UTC)

    @staticmethod
    def _extract_schema_version(firmware_version: str) -> str:
        """
        Extract schema version from firmware version.

        Schema version is derived from firmware major.minor.patch.
        Example: "28.0.3.46454 epdbuild..." -> "28.0.3"
        """
        if not firmware_version:
            return "unknown"

        # Extract first 3 version components (major.minor.patch)
        parts = firmware_version.split()[0].split(".")
        if len(parts) >= 3:
            return ".".join(parts[:3])
        return firmware_version.split()[0] if firmware_version else "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "device_id": self.device_id,
            "ip": self.ip,
            "name": self.name,
            "model": self.model,
            "mac_address": self.mac_address,
            "firmware_version": self.firmware_version,
            "schema_version": self.schema_version,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class DeviceRepository(BaseRepository):
    """Repository for device persistence."""

    async def _create_schema(self) -> None:
        """Create devices table and indexes."""
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT UNIQUE NOT NULL,
                ip TEXT NOT NULL,
                name TEXT NOT NULL,
                model TEXT NOT NULL,
                mac_address TEXT NOT NULL,
                firmware_version TEXT NOT NULL,
                schema_version TEXT,
                last_seen TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: Add schema_version column if it doesn't exist
        try:
            await self._db.execute("SELECT schema_version FROM devices LIMIT 1")
        except aiosqlite.OperationalError:
            logger.info("Migrating devices table: Adding schema_version column")
            await self._db.execute("""
                ALTER TABLE devices ADD COLUMN schema_version TEXT
            """)
            await self._db.commit()

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_ip ON devices(ip)
        """)

        await self._db.commit()

    async def upsert(self, device: Device) -> Device:
        """
        Insert or update device.

        Args:
            device: Device to upsert

        Returns:
            Device with updated id
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            INSERT INTO devices (device_id, ip, name, model, mac_address, firmware_version, schema_version, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                ip = excluded.ip,
                name = excluded.name,
                model = excluded.model,
                firmware_version = excluded.firmware_version,
                schema_version = excluded.schema_version,
                last_seen = excluded.last_seen,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """,
            (
                device.device_id,
                device.ip,
                device.name,
                device.model,
                device.mac_address,
                device.firmware_version,
                device.schema_version,
                device.last_seen,
            ),
        )

        row = await cursor.fetchone()
        device.id = row[0] if row else None

        await db.commit()
        logger.debug(f"Upserted device: {device.name} ({device.device_id})")

        return device

    async def get_all(self) -> List[Device]:
        """Get all devices."""
        db = self._ensure_initialized()

        cursor = await db.execute("""
            SELECT id, device_id, ip, name, model, mac_address, firmware_version, schema_version, last_seen
            FROM devices
            ORDER BY last_seen DESC
        """)

        rows = await cursor.fetchall()

        devices = [
            Device(
                id=row[0],
                device_id=row[1],
                ip=row[2],
                name=row[3],
                model=row[4],
                mac_address=row[5],
                firmware_version=row[6],
                schema_version=row[7],
                last_seen=datetime.fromisoformat(row[8]) if row[8] else None,
            )
            for row in rows
        ]

        return devices

    async def get_by_device_id(self, device_id: str) -> Optional[Device]:
        """Get device by device_id."""
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT id, device_id, ip, name, model, mac_address, firmware_version, schema_version, last_seen
            FROM devices
            WHERE device_id = ?
        """,
            (device_id,),
        )

        row = await cursor.fetchone()

        if not row:
            return None

        return Device(
            id=row[0],
            device_id=row[1],
            ip=row[2],
            name=row[3],
            model=row[4],
            mac_address=row[5],
            firmware_version=row[6],
            schema_version=row[7],
            last_seen=datetime.fromisoformat(row[8]) if row[8] else None,
        )

    async def delete_all(self) -> int:
        """Delete all devices from database. Returns number of deleted rows."""
        db = self._ensure_initialized()

        cursor = await db.execute("DELETE FROM devices")
        await db.commit()

        deleted_count = cursor.rowcount
        logger.debug(f"Deleted all devices from database: {deleted_count} rows")

        return deleted_count
