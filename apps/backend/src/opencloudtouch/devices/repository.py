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
        setup_status: str = "unknown",
        ssh_permanent: bool = False,
        setup_completed_at: Optional[datetime] = None,
        marge_account_uuid: Optional[str] = None,
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
        self.setup_status = setup_status
        self.ssh_permanent = ssh_permanent
        self.setup_completed_at = setup_completed_at
        self.marge_account_uuid = marge_account_uuid

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
            "setup_status": self.setup_status,
            "ssh_permanent": self.ssh_permanent,
            "setup_completed_at": (
                self.setup_completed_at.isoformat() if self.setup_completed_at else None
            ),
            "marge_account_uuid": self.marge_account_uuid,
        }


class DeviceRepository(BaseRepository):
    """Repository for device persistence."""

    async def _create_schema(self) -> None:
        """Create devices table, indexes, and apply migrations."""
        await self._conn.execute("""
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

        # Legacy migration: schema_version (pre-migration-framework)
        try:
            await self._conn.execute("SELECT schema_version FROM devices LIMIT 1")
        except aiosqlite.OperationalError:
            logger.info("Migrating devices table: Adding schema_version column")
            await self._conn.execute(
                "ALTER TABLE devices ADD COLUMN schema_version TEXT"
            )
            await self._conn.commit()

        # Migrations v100–v199 reserved for devices
        await self._apply_migration(
            version=100,
            description="Add setup_status column to devices",
            sql="ALTER TABLE devices ADD COLUMN setup_status TEXT DEFAULT 'unknown'",
        )
        await self._apply_migration(
            version=101,
            description="Add ssh_permanent column to devices",
            sql="ALTER TABLE devices ADD COLUMN ssh_permanent INTEGER DEFAULT 0",
        )
        await self._apply_migration(
            version=102,
            description="Add setup_completed_at column to devices",
            sql="ALTER TABLE devices ADD COLUMN setup_completed_at TIMESTAMP",
        )
        await self._apply_migration(
            version=103,
            description="Add marge_account_uuid column to devices",
            sql="ALTER TABLE devices ADD COLUMN marge_account_uuid TEXT",
        )

        await self._apply_migration(
            version=103,
            description="Add marge_account_uuid column to devices",
            sql="ALTER TABLE devices ADD COLUMN marge_account_uuid TEXT",
        )

        # Indexes
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id)
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ip ON devices(ip)
        """)

        await self._conn.commit()

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
            INSERT INTO devices (device_id, ip, name, model, mac_address, firmware_version, schema_version, last_seen, marge_account_uuid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                ip = excluded.ip,
                name = excluded.name,
                model = excluded.model,
                firmware_version = excluded.firmware_version,
                schema_version = excluded.schema_version,
                last_seen = excluded.last_seen,
                marge_account_uuid = COALESCE(excluded.marge_account_uuid, devices.marge_account_uuid),
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
                device.marge_account_uuid,
            ),
        )

        row = await cursor.fetchone()
        device.id = row[0] if row else None

        await db.commit()
        logger.debug("Upserted device: %s (%s)", device.name, device.device_id)

        return device

    async def get_all(self) -> List[Device]:
        """Get all devices."""
        db = self._ensure_initialized()

        cursor = await db.execute("""
            SELECT id, device_id, ip, name, model, mac_address, firmware_version,
                   schema_version, last_seen, setup_status, ssh_permanent,
                   setup_completed_at, marge_account_uuid
            FROM devices
            ORDER BY last_seen DESC
        """)

        rows = await cursor.fetchall()
        return [self._row_to_device(row) for row in rows]

    async def get_by_device_id(self, device_id: str) -> Optional[Device]:
        """Get device by device_id."""
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT id, device_id, ip, name, model, mac_address, firmware_version,
                   schema_version, last_seen, setup_status, ssh_permanent,
                   setup_completed_at, marge_account_uuid
            FROM devices
            WHERE device_id = ?
        """,
            (device_id,),
        )

        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_device(row)

    async def update_setup_status(
        self,
        device_id: str,
        setup_status: str,
        ssh_permanent: Optional[bool] = None,
        setup_completed_at: Optional[datetime] = None,
    ) -> None:
        """Update setup-related fields for a device.

        Only updates fields that are explicitly provided (not None).
        """
        db = self._ensure_initialized()

        fields = ["setup_status = ?"]
        params: list = [setup_status]

        if ssh_permanent is not None:
            fields.append("ssh_permanent = ?")
            params.append(int(ssh_permanent))

        if setup_completed_at is not None:
            fields.append("setup_completed_at = ?")
            params.append(setup_completed_at.isoformat())

        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(device_id)

        await db.execute(
            f"UPDATE devices SET {', '.join(fields)} WHERE device_id = ?",  # nosec B608 - field names are hardcoded constants
            params,
        )
        await db.commit()
        logger.info("Updated setup status for %s: %s", device_id, setup_status)

    async def get_by_account_uuid(self, account_uuid: str) -> Optional[Device]:
        """Get device by marge_account_uuid."""
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT id, device_id, ip, name, model, mac_address, firmware_version,
                   schema_version, last_seen, setup_status, ssh_permanent,
                   setup_completed_at, marge_account_uuid
            FROM devices
            WHERE marge_account_uuid = ?
        """,
            (account_uuid,),
        )

        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_device(row)

    async def update_marge_account_uuid(
        self, device_id: str, marge_account_uuid: str
    ) -> None:
        """Update marge_account_uuid for a device."""
        db = self._ensure_initialized()

        await db.execute(
            "UPDATE devices SET marge_account_uuid = ?, updated_at = CURRENT_TIMESTAMP WHERE device_id = ?",
            (marge_account_uuid, device_id),
        )
        await db.commit()
        logger.info(
            "Updated marge_account_uuid for %s: %s", device_id, marge_account_uuid
        )

    async def get_by_marge_account_uuid(
        self, marge_account_uuid: str
    ) -> Optional[Device]:
        """Get device by its marge account UUID (margeAccountUUID).

        This is the account ID that SoundTouch devices use when calling
        /streaming/account/{account_id}/full on boot.

        Args:
            marge_account_uuid: The account UUID (e.g., "5522049")

        Returns:
            Device if found, None otherwise
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT id, device_id, ip, name, model, mac_address, firmware_version,
                   schema_version, last_seen, setup_status, ssh_permanent,
                   setup_completed_at, marge_account_uuid
            FROM devices
            WHERE marge_account_uuid = ?
        """,
            (marge_account_uuid,),
        )

        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_device(row)

    async def delete_all(self) -> int:
        """Delete all devices from database. Returns number of deleted rows."""
        db = self._ensure_initialized()

        cursor = await db.execute("DELETE FROM devices")
        await db.commit()

        deleted_count = cursor.rowcount
        logger.debug("Deleted all devices from database: %d rows", deleted_count)

        return deleted_count

    async def delete_by_device_id(self, device_id: str) -> None:
        db = self._ensure_initialized()

        await db.execute("DELETE FROM devices WHERE device_id = ? ", (device_id,))
        await db.commit()

        logger.debug("Deleted device %s from database", device_id)

    @staticmethod
    def _row_to_device(row: tuple | Any) -> Device:
        """Map a database row to a Device model.

        Column order: id, device_id, ip, name, model, mac_address,
        firmware_version, schema_version, last_seen, setup_status,
        ssh_permanent, setup_completed_at, marge_account_uuid.
        """
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
            setup_status=row[9] or "unknown",
            ssh_permanent=bool(row[10]) if row[10] is not None else False,
            setup_completed_at=(datetime.fromisoformat(row[11]) if row[11] else None),
            marge_account_uuid=row[12] if len(row) > 12 else None,
        )
