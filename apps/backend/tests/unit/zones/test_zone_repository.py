"""Unit tests for ZoneRepository."""

import pytest

from opencloudtouch.devices.repository import Device, DeviceRepository
from opencloudtouch.zones.repository import ZoneRepository


@pytest.mark.asyncio
class TestZoneRepository:
    """Tests for ZoneRepository CRUD operations."""

    @pytest.fixture
    async def repo(self, tmp_path):
        """Create a ZoneRepository with temporary database."""
        db_path = tmp_path / "test_zones.db"
        repository = ZoneRepository(str(db_path))
        await repository.initialize()
        yield repository
        await repository.close()

    async def test_create_zone(self, repo):
        """Create a new zone with master."""
        zone = await repo.create_zone("MASTER_001")

        assert zone.id is not None
        assert zone.master_device_id == "MASTER_001"
        assert zone.is_active()

        members = await repo.get_active_members(zone.id)
        assert len(members) == 1
        assert members[0].device_id == "MASTER_001"
        assert members[0].role == "master"

    async def test_add_member(self, repo):
        """Add a slave to a zone."""
        zone = await repo.create_zone("MASTER_001")
        member = await repo.add_member(zone.id, "SLAVE_001", "slave")

        assert member.device_id == "SLAVE_001"
        assert member.role == "slave"

    async def test_remove_member(self, repo):
        """Remove a member from a zone."""
        zone = await repo.create_zone("MASTER_001")
        await repo.add_member(zone.id, "SLAVE_001", "slave")

        await repo.remove_member(zone.id, "SLAVE_001")

        members = await repo.get_active_members(zone.id)
        assert len(members) == 1  # Only master left
        assert members[0].device_id == "MASTER_001"

    async def test_dissolve_zone_hard_deletes_zone_and_members(self, repo):
        """Dissolving a zone permanently deletes the zone and its members."""
        zone = await repo.create_zone("MASTER_001")
        await repo.add_member(zone.id, "SLAVE_001", "slave")

        await repo.dissolve_zone(zone.id)

        db = repo._ensure_initialized()

        cursor = await db.execute(
            "SELECT COUNT(*) FROM zones WHERE id = ?",
            (zone.id,),
        )
        assert (await cursor.fetchone())[0] == 0

        cursor = await db.execute(
            "SELECT COUNT(*) FROM zone_members WHERE zone_id = ?",
            (zone.id,),
        )
        assert (await cursor.fetchone())[0] == 0

    async def test_dissolve_zone_is_idempotent(self, repo):
        """Dissolving an already deleted zone does not fail."""
        zone = await repo.create_zone("MASTER_001")

        await repo.dissolve_zone(zone.id)
        await repo.dissolve_zone(zone.id)

        db = repo._ensure_initialized()
        cursor = await db.execute(
            "SELECT COUNT(*) FROM zones WHERE id = ?",
            (zone.id,),
        )
        assert (await cursor.fetchone())[0] == 0

    async def test_recreate_zone_after_dissolution_gets_new_id(self, repo):
        """Recreating a dissolved zone creates a new database row."""
        old_zone = await repo.create_zone("MASTER_001")
        old_zone_id = old_zone.id

        await repo.dissolve_zone(old_zone_id)
        new_zone = await repo.create_zone("MASTER_001")

        assert new_zone.id is not None
        assert new_zone.id != old_zone_id

    async def test_startup_cleanup_removes_previously_dissolved_zones(self, repo):
        """Startup migration removes legacy soft-deleted zones and members."""
        db = repo._ensure_initialized()

        cursor = await db.execute(
            """
            INSERT INTO zones (master_device_id, created_at, dissolved_at)
            VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("OLD_MASTER",),
        )
        old_zone_id = cursor.lastrowid
        assert old_zone_id is not None

        await db.execute(
            """
            INSERT INTO zone_members (zone_id, device_id, role, added_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (old_zone_id, "OLD_MASTER", "master"),
        )

        # Simulate a database that predates cleanup migrations 205/206.
        await db.execute(
            "DELETE FROM schema_versions WHERE version IN (205, 206)"
        )
        await db.commit()

        db_path = repo.db_path
        await repo.close()

        reopened = ZoneRepository(db_path)
        await reopened.initialize()
        try:
            reopened_db = reopened._ensure_initialized()

            cursor = await reopened_db.execute(
                "SELECT COUNT(*) FROM zones WHERE id = ?",
                (old_zone_id,),
            )
            assert (await cursor.fetchone())[0] == 0

            cursor = await reopened_db.execute(
                "SELECT COUNT(*) FROM zone_members WHERE zone_id = ?",
                (old_zone_id,),
            )
            assert (await cursor.fetchone())[0] == 0
        finally:
            await reopened.close()

    async def test_dissolve_zone_with_no_members(self, repo):
        """Dissolving a zone with no members still deletes the zone."""
        zone = await repo.create_zone("MASTER_001")
        db = repo._ensure_initialized()

        await db.execute(
            "DELETE FROM zone_members WHERE zone_id = ?",
            (zone.id,),
        )
        await db.commit()

        await repo.dissolve_zone(zone.id)

        cursor = await db.execute(
            "SELECT COUNT(*) FROM zones WHERE id = ?",
            (zone.id,),
        )
        assert (await cursor.fetchone())[0] == 0

    async def test_concurrent_dissolve_zone_is_safe(self, repo):
        """Concurrent dissolution attempts are idempotent and safe."""
        import asyncio

        zone = await repo.create_zone("MASTER_001")
        await repo.add_member(zone.id, "SLAVE_001", "slave")

        await asyncio.gather(
            repo.dissolve_zone(zone.id),
            repo.dissolve_zone(zone.id),
        )

        db = repo._ensure_initialized()

        cursor = await db.execute(
            "SELECT COUNT(*) FROM zones WHERE id = ?",
            (zone.id,),
        )
        assert (await cursor.fetchone())[0] == 0

        cursor = await db.execute(
            "SELECT COUNT(*) FROM zone_members WHERE zone_id = ?",
            (zone.id,),
        )
        assert (await cursor.fetchone())[0] == 0

    async def test_dissolve_zone_keeps_device_records(self, repo):
        """Dissolving a zone must not delete the underlying devices."""
        device_repo = DeviceRepository(repo.db_path)
        await device_repo.initialize()

        try:
            master = Device(
                device_id="MASTER_001",
                ip="192.168.1.10",
                name="Master",
                model="SoundTouch 10",
                mac_address="AA:BB:CC:DD:EE:01",
                firmware_version="27.0.6",
            )
            slave = Device(
                device_id="SLAVE_001",
                ip="192.168.1.11",
                name="Slave",
                model="SoundTouch 10",
                mac_address="AA:BB:CC:DD:EE:02",
                firmware_version="27.0.6",
            )

            await device_repo.upsert(master)
            await device_repo.upsert(slave)

            zone = await repo.create_zone(master.device_id)
            await repo.add_member(zone.id, slave.device_id, "slave")

            await repo.dissolve_zone(zone.id)

            assert await device_repo.get_by_device_id(master.device_id) is not None
            assert await device_repo.get_by_device_id(slave.device_id) is not None

            db = repo._ensure_initialized()
            cursor = await db.execute(
                "SELECT COUNT(*) FROM zone_members WHERE zone_id = ?",
                (zone.id,),
            )
            assert (await cursor.fetchone())[0] == 0
        finally:
            await device_repo.close()

    async def test_get_active_zone_by_master(self, repo):
        """Get active zone by master device ID."""
        zone = await repo.create_zone("MASTER_001")

        fetched = await repo.get_active_zone_by_master("MASTER_001")

        assert fetched is not None
        assert fetched.id == zone.id
        assert fetched.master_device_id == "MASTER_001"

    async def test_get_active_zone_by_device_slave(self, repo):
        """Get active zone by slave device ID."""
        zone = await repo.create_zone("MASTER_001")
        await repo.add_member(zone.id, "SLAVE_001", "slave")

        fetched = await repo.get_active_zone_by_device("SLAVE_001")

        assert fetched is not None
        assert fetched.id == zone.id

    async def test_get_active_zone_by_device_returns_none(self, repo):
        """Returns None when device is not in any zone."""
        fetched = await repo.get_active_zone_by_device("ORPHAN")
        assert fetched is None

    async def test_get_all_active_zones(self, repo):
        """Get all active zones."""
        await repo.create_zone("MASTER_001")
        await repo.create_zone("MASTER_002")
        zone3 = await repo.create_zone("MASTER_003")
        await repo.dissolve_zone(zone3.id)

        active_zones = await repo.get_all_active_zones()

        assert len(active_zones) == 2
        master_ids = {z.master_device_id for z in active_zones}
        assert "MASTER_001" in master_ids
        assert "MASTER_002" in master_ids
        assert "MASTER_003" not in master_ids

    async def test_get_active_members_ordered_by_role(self, repo):
        """Active members are returned with master first."""
        zone = await repo.create_zone("MASTER_001")
        await repo.add_member(zone.id, "SLAVE_001", "slave")
        await repo.add_member(zone.id, "SLAVE_002", "slave")

        members = await repo.get_active_members(zone.id)

        assert len(members) == 3
        assert members[0].role == "master"
        assert members[0].device_id == "MASTER_001"
        assert members[1].role == "slave"
        assert members[2].role == "slave"
