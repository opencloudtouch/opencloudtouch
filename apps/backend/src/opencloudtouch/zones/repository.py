"""Zone repository for multi-room zone persistence."""

import logging
from datetime import UTC, datetime
from typing import List, Optional

from opencloudtouch.core.repository import BaseRepository

logger = logging.getLogger(__name__)


class Zone:
    """Zone entity representing a multi-room zone."""

    def __init__(
        self,
        master_device_id: str,
        created_at: datetime,
        dissolved_at: Optional[datetime] = None,
        id: Optional[int] = None,
    ):
        self.id = id
        self.master_device_id = master_device_id
        self.created_at = created_at
        self.dissolved_at = dissolved_at

    def is_active(self) -> bool:
        """Check if zone is currently active (not dissolved)."""
        return self.dissolved_at is None

    def to_dict(self) -> dict:
        """Convert zone to dictionary."""
        return {
            "id": self.id,
            "master_device_id": self.master_device_id,
            "created_at": self.created_at.isoformat(),
            "dissolved_at": (
                self.dissolved_at.isoformat() if self.dissolved_at else None
            ),
        }


class ZoneMember:
    """Zone member entity."""

    def __init__(
        self,
        zone_id: int,
        device_id: str,
        role: str,
        added_at: datetime,
        removed_at: Optional[datetime] = None,
        id: Optional[int] = None,
    ):
        self.id = id
        self.zone_id = zone_id
        self.device_id = device_id
        self.role = role  # 'master' or 'slave'
        self.added_at = added_at
        self.removed_at = removed_at


class ZoneRepository(BaseRepository):
    """Repository for zone and zone member persistence."""

    async def _create_schema(self) -> None:
        """Create zones and zone_members tables."""
        # Migrations v200-v299 reserved for zones
        await self._apply_migration(
            version=200,
            description="Create zones table",
            sql="""
                CREATE TABLE IF NOT EXISTS zones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    master_device_id TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    dissolved_at TIMESTAMP NULL
                )
            """,
        )

        await self._apply_migration(
            version=201,
            description="Create zone_members table",
            sql="""
                CREATE TABLE IF NOT EXISTS zone_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_id INTEGER NOT NULL,
                    device_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('master', 'slave')),
                    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    removed_at TIMESTAMP NULL,
                    FOREIGN KEY (zone_id) REFERENCES zones(id)
                )
            """,
        )

        await self._apply_migration(
            version=202,
            description="Create index on zones.master_device_id",
            sql="CREATE INDEX IF NOT EXISTS idx_zones_master ON zones(master_device_id)",
        )

        await self._apply_migration(
            version=203,
            description="Create index on zone_members.zone_id",
            sql="CREATE INDEX IF NOT EXISTS idx_zone_members_zone ON zone_members(zone_id)",
        )

        await self._apply_migration(
            version=204,
            description="Create index on zone_members.device_id",
            sql="CREATE INDEX IF NOT EXISTS idx_zone_members_device ON zone_members(device_id)",
        )

        await self._conn.commit()

    async def create_zone(self, master_device_id: str) -> Zone:
        """Create a new zone with the given master device."""
        db = self._ensure_initialized()

        cursor = await db.execute(
            "INSERT INTO zones (master_device_id, created_at) VALUES (?, ?)",
            (master_device_id, datetime.now(UTC)),
        )
        await db.commit()

        zone = Zone(
            master_device_id=master_device_id,
            created_at=datetime.now(UTC),
            id=cursor.lastrowid,
        )

        # Create master member
        if zone.id is None:
            raise RuntimeError("Zone has no ID after INSERT")
        await self.add_member(zone.id, master_device_id, "master")

        logger.info("Created zone %d with master %s", zone.id, master_device_id)
        return zone

    async def add_member(
        self, zone_id: int, device_id: str, role: str = "slave"
    ) -> ZoneMember:
        """Add a device to a zone."""
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            INSERT INTO zone_members (zone_id, device_id, role, added_at)
            VALUES (?, ?, ?, ?)
            """,
            (zone_id, device_id, role, datetime.now(UTC)),
        )
        await db.commit()

        member = ZoneMember(
            zone_id=zone_id,
            device_id=device_id,
            role=role,
            added_at=datetime.now(UTC),
            id=cursor.lastrowid,
        )

        logger.debug("Added %s to zone %d as %s", device_id, zone_id, role)
        return member

    async def remove_member(self, zone_id: int, device_id: str) -> None:
        """Remove a device from a zone (soft delete)."""
        db = self._ensure_initialized()

        await db.execute(
            """
            UPDATE zone_members
            SET removed_at = ?
            WHERE zone_id = ? AND device_id = ? AND removed_at IS NULL
            """,
            (datetime.now(UTC), zone_id, device_id),
        )
        await db.commit()

        logger.debug("Removed %s from zone %d", device_id, zone_id)

    async def dissolve_zone(self, zone_id: int) -> None:
        """Dissolve a zone (soft delete)."""
        db = self._ensure_initialized()

        now = datetime.now(UTC)

        # Mark zone as dissolved
        await db.execute(
            "UPDATE zones SET dissolved_at = ? WHERE id = ? AND dissolved_at IS NULL",
            (now, zone_id),
        )

        # Remove all members
        await db.execute(
            """
            UPDATE zone_members
            SET removed_at = ?
            WHERE zone_id = ? AND removed_at IS NULL
            """,
            (now, zone_id),
        )

        await db.commit()
        logger.info("Dissolved zone %d", zone_id)

    async def get_active_zone_by_master(self, master_device_id: str) -> Optional[Zone]:
        """Get active zone by master device ID."""
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT id, master_device_id, created_at, dissolved_at
            FROM zones
            WHERE master_device_id = ? AND dissolved_at IS NULL
            """,
            (master_device_id,),
        )

        row = await cursor.fetchone()
        if not row:
            return None

        return Zone(
            id=row[0],
            master_device_id=row[1],
            created_at=row[2],
            dissolved_at=row[3],
        )

    async def get_active_zone_by_device(self, device_id: str) -> Optional[Zone]:
        """Get active zone by any device ID (master or slave)."""
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT z.id, z.master_device_id, z.created_at, z.dissolved_at
            FROM zones z
            JOIN zone_members zm ON zm.zone_id = z.id
            WHERE zm.device_id = ?
              AND zm.removed_at IS NULL
              AND z.dissolved_at IS NULL
            LIMIT 1
            """,
            (device_id,),
        )

        row = await cursor.fetchone()
        if not row:
            return None

        return Zone(
            id=row[0],
            master_device_id=row[1],
            created_at=row[2],
            dissolved_at=row[3],
        )

    async def get_active_members(self, zone_id: int) -> List[ZoneMember]:
        """Get all active members of a zone, ordered by role (master first)."""
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT id, zone_id, device_id, role, added_at, removed_at
            FROM zone_members
            WHERE zone_id = ? AND removed_at IS NULL
            ORDER BY CASE WHEN role='master' THEN 0 ELSE 1 END, added_at ASC
            """,
            (zone_id,),
        )

        rows = await cursor.fetchall()
        return [
            ZoneMember(
                id=row[0],
                zone_id=row[1],
                device_id=row[2],
                role=row[3],
                added_at=row[4],
                removed_at=row[5],
            )
            for row in rows
        ]

    async def get_all_active_zones(self) -> List[Zone]:
        """Get all active zones."""
        db = self._ensure_initialized()

        cursor = await db.execute("""
            SELECT id, master_device_id, created_at, dissolved_at
            FROM zones
            WHERE dissolved_at IS NULL
            ORDER BY created_at DESC
            """)

        rows = await cursor.fetchall()
        return [
            Zone(
                id=row[0],
                master_device_id=row[1],
                created_at=row[2],
                dissolved_at=row[3],
            )
            for row in rows
        ]
