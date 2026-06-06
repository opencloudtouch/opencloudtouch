"""Unit tests for ZoneRepository."""

import pytest

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

    async def test_dissolve_zone(self, repo):
        """Dissolve a zone (soft delete)."""
        zone = await repo.create_zone("MASTER_001")
        await repo.add_member(zone.id, "SLAVE_001", "slave")

        await repo.dissolve_zone(zone.id)

        active_zones = await repo.get_all_active_zones()
        assert len(active_zones) == 0

        members = await repo.get_active_members(zone.id)
        assert len(members) == 0

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
