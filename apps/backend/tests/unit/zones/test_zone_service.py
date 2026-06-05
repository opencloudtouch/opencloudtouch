"""Unit tests for ZoneService."""

from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.devices.repository import Device
from opencloudtouch.zones.models import ZoneMemberInfo, ZoneStatus
from opencloudtouch.zones.service import ZoneService


def _make_device(
    device_id="DEV001", ip="192.168.1.100", name="Speaker 1", model="SoundTouch 10"
):
    """Create a test Device."""
    return Device(
        device_id=device_id,
        ip=ip,
        name=name,
        model=model,
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="28.0.3.46454",
    )


def _make_zone_status(master_id="DEV001", master_ip="192.168.1.100", members=None):
    """Create a test ZoneStatus."""
    if members is None:
        members = [
            ZoneMemberInfo(
                device_id="DEV001", ip_address="192.168.1.100", role="master"
            ),
            ZoneMemberInfo(
                device_id="DEV002", ip_address="192.168.1.101", role="slave"
            ),
        ]
    return ZoneStatus(
        master_id=master_id,
        master_ip=master_ip,
        is_master=True,
        members=members,
    )


def _make_service():
    """Create ZoneService with mocked repos."""
    device_repo = AsyncMock()
    zone_repo = AsyncMock()
    service = ZoneService(device_repo=device_repo, zone_repo=zone_repo)
    return service, device_repo, zone_repo


class TestGetZoneStatus:
    """Tests for get_zone_status."""

    @pytest.mark.asyncio
    async def test_returns_zone_status(self):
        """Returns enriched zone status for a device."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100", "Living Room")
        dev2 = _make_device("DEV002", "192.168.1.101", "Kitchen")
        device_repo.get_by_device_id.return_value = dev1
        device_repo.get_all.return_value = [dev1, dev2]

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = _make_zone_status()

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.get_zone_status("DEV001")

        assert result is not None
        assert result.master_id == "DEV001"
        assert result.members[0].name == "Living Room"
        assert result.members[1].name == "Kitchen"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_in_zone(self):
        """Returns None when device has no zone."""
        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.return_value = _make_device()

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = None

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.get_zone_status("DEV001")

        assert result is None

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_device(self):
        """Raises DeviceNotFoundError for unknown device ID."""
        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await service.get_zone_status("UNKNOWN")


class TestGetAllZones:
    """Tests for get_all_zones (DB-backed)."""

    @pytest.mark.asyncio
    async def test_returns_all_zones_from_db(self):
        """Returns zones from database with enriched device info."""
        from datetime import UTC, datetime

        from opencloudtouch.zones.repository import Zone, ZoneMember

        service, device_repo, zone_repo = _make_service()

        # Setup devices
        dev1 = _make_device("DEV001", "192.168.1.100", "Living Room")
        dev2 = _make_device("DEV002", "192.168.1.101", "Kitchen")
        device_repo.get_all.return_value = [dev1, dev2]
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }.get(did)

        # Setup DB zones
        zone1 = Zone(
            id=1,
            master_device_id="DEV001",
            created_at=datetime.now(UTC),
        )
        zone_repo.get_all_active_zones.return_value = [zone1]

        # Setup zone members
        members = [
            ZoneMember(
                zone_id=1,
                device_id="DEV001",
                role="master",
                added_at=datetime.now(UTC),
            ),
            ZoneMember(
                zone_id=1,
                device_id="DEV002",
                role="slave",
                added_at=datetime.now(UTC),
            ),
        ]
        zone_repo.get_active_members.return_value = members

        result = await service.get_all_zones()

        assert len(result) == 1
        assert result[0].master_id == "DEV001"
        assert len(result[0].members) == 2
        assert result[0].members[0].name == "Living Room"
        assert result[0].members[1].name == "Kitchen"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_zones_in_db(self):
        """Returns empty list when no zones exist in database."""
        service, device_repo, zone_repo = _make_service()
        zone_repo.get_all_active_zones.return_value = []

        result = await service.get_all_zones()
        assert result == []


class TestCreateZone:
    """Tests for create_zone."""

    @pytest.mark.asyncio
    async def test_creates_zone_successfully(self):
        """Creates zone and returns enriched status."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100", "Living Room")
        dev2 = _make_device("DEV002", "192.168.1.101", "Kitchen")
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]
        device_repo.get_all.return_value = [dev1, dev2]

        mock_client = AsyncMock()
        mock_client.create_zone.return_value = _make_zone_status()

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.create_zone("DEV001", ["DEV002"])

        assert result.master_id == "DEV001"
        assert len(result.members) == 2

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_master(self):
        """Raises DeviceNotFoundError when master not found."""
        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await service.create_zone("UNKNOWN", ["DEV002"])

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_slave(self):
        """Raises DeviceNotFoundError when a slave is not found."""
        service, device_repo, zone_repo = _make_service()
        master = _make_device("DEV001")
        device_repo.get_by_device_id.side_effect = lambda did: (
            master if did == "DEV001" else None
        )

        with pytest.raises(DeviceNotFoundError):
            await service.create_zone("DEV001", ["UNKNOWN"])

    @pytest.mark.asyncio
    async def test_raises_connection_error_on_failure(self):
        """Raises DeviceConnectionError when creation fails."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001")
        dev2 = _make_device("DEV002", "192.168.1.101")
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]

        mock_client = AsyncMock()
        mock_client.create_zone.side_effect = Exception("Timeout")

        with patch.object(service, "_get_client", return_value=mock_client):
            with pytest.raises(DeviceConnectionError):
                await service.create_zone("DEV001", ["DEV002"])


class TestAddMembers:
    """Tests for add_members."""

    @pytest.mark.asyncio
    async def test_adds_members_successfully(self):
        """Adds members to zone without error."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001")
        dev3 = _make_device("DEV003", "192.168.1.102")
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV003": dev3,
        }[did]

        mock_client = AsyncMock()
        with patch.object(service, "_get_client", return_value=mock_client):
            await service.add_members("DEV001", ["DEV003"])

        mock_client.add_zone_members.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_device(self):
        """Raises DeviceNotFoundError for unknown slave."""
        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.side_effect = lambda did: (
            _make_device() if did == "DEV001" else None
        )

        with pytest.raises(DeviceNotFoundError):
            await service.add_members("DEV001", ["UNKNOWN"])


class TestRemoveMembers:
    """Tests for remove_members."""

    @pytest.mark.asyncio
    async def test_removes_members_successfully(self):
        """Removes members from zone without error."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001")
        dev2 = _make_device("DEV002", "192.168.1.101")
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]

        mock_client = AsyncMock()
        with patch.object(service, "_get_client", return_value=mock_client):
            await service.remove_members("DEV001", ["DEV002"])

        mock_client.remove_zone_members.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_connection_error_on_failure(self):
        """Raises DeviceConnectionError when remove fails."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001")
        dev2 = _make_device("DEV002", "192.168.1.101")
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]

        mock_client = AsyncMock()
        mock_client.remove_zone_members.side_effect = Exception("Error")

        with patch.object(service, "_get_client", return_value=mock_client):
            with pytest.raises(DeviceConnectionError):
                await service.remove_members("DEV001", ["DEV002"])


class TestDissolveZone:
    """Tests for dissolve_zone."""

    @pytest.mark.asyncio
    async def test_dissolves_zone_successfully(self):
        """Dissolves zone by removing slaves sequentially, then master."""
        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.return_value = _make_device()

        # Mock zone status with master + 2 slaves
        zone_status = ZoneStatus(
            master_id="DEV001",
            master_ip="192.168.1.100",
            is_master=True,
            members=[
                ZoneMemberInfo(
                    device_id="DEV001", ip_address="192.168.1.100", role="master"
                ),
                ZoneMemberInfo(
                    device_id="DEV002", ip_address="192.168.1.101", role="slave"
                ),
                ZoneMemberInfo(
                    device_id="DEV003", ip_address="192.168.1.102", role="slave"
                ),
            ],
        )

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = zone_status
        with patch.object(service, "_get_client", return_value=mock_client):
            await service.dissolve_zone("DEV001")

        # Should call get_zone_status first
        mock_client.get_zone_status.assert_called_once()
        # Should remove each slave individually
        assert mock_client.remove_zone_members.call_count == 2
        # Then remove zone on master
        mock_client.remove_zone.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_device(self):
        """Raises DeviceNotFoundError for unknown master."""
        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await service.dissolve_zone("UNKNOWN")


class TestChangeMaster:
    """Tests for change_master."""

    @pytest.mark.asyncio
    async def test_changes_master_successfully(self):
        """Dissolves old zone and creates new one with new master."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100", "Living Room")
        dev2 = _make_device("DEV002", "192.168.1.101", "Kitchen")
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]
        device_repo.get_all.return_value = [dev1, dev2]

        old_zone = _make_zone_status()
        new_zone = _make_zone_status(
            "DEV002",
            "192.168.1.101",
            [
                ZoneMemberInfo(
                    device_id="DEV002", ip_address="192.168.1.101", role="master"
                ),
                ZoneMemberInfo(
                    device_id="DEV001", ip_address="192.168.1.100", role="slave"
                ),
            ],
        )

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = old_zone
        mock_client.create_zone.return_value = new_zone

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.change_master("DEV001", "DEV002")

        assert result.master_id == "DEV002"
        mock_client.remove_zone.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_value_error_when_not_in_zone(self):
        """Raises ValueError when device is not in a zone."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001")
        dev2 = _make_device("DEV002", "192.168.1.101")
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = None

        with patch.object(service, "_get_client", return_value=mock_client):
            with pytest.raises(ValueError, match="not in a zone"):
                await service.change_master("DEV001", "DEV002")


class TestGetClientFallback:
    """Tests for _get_client fallback branch (no client_factory)."""

    def test_get_client_fallback_when_factory_is_none(self):
        """Uses lazy import fallback when client_factory is None."""
        device_repo = AsyncMock()
        zone_repo = AsyncMock()
        service = ZoneService(
            device_repo=device_repo, zone_repo=zone_repo, client_factory=None
        )

        with patch(
            "opencloudtouch.devices.adapter.get_device_client"
        ) as mock_get_client:
            mock_get_client.return_value = AsyncMock()
            result = service._get_client("192.168.1.100")

        mock_get_client.assert_called_once_with("http://192.168.1.100:8090")
        assert result is mock_get_client.return_value


class TestGetZoneStatusConnectionError:
    """Tests for get_zone_status DeviceConnectionError branch."""

    @pytest.mark.asyncio
    async def test_raises_connection_error_on_client_exception(self):
        """Raises DeviceConnectionError when client.get_zone_status() fails."""
        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.return_value = _make_device()

        mock_client = AsyncMock()
        mock_client.get_zone_status.side_effect = Exception("Connection refused")

        with patch.object(service, "_get_client", return_value=mock_client):
            with pytest.raises(DeviceConnectionError):
                await service.get_zone_status("DEV001")


class TestGetAllZonesEdgeCases:
    """Tests for get_all_zones edge cases."""

    @pytest.mark.asyncio
    async def test_skips_zone_without_id(self):
        """Skips zones from DB that have no ID (logs error)."""
        from datetime import UTC, datetime

        from opencloudtouch.zones.repository import Zone

        service, device_repo, zone_repo = _make_service()
        device_repo.get_all.return_value = []

        # Zone with id=None
        zone_no_id = Zone(
            id=None,
            master_device_id="DEV001",
            created_at=datetime.now(UTC),
        )
        zone_repo.get_all_active_zones.return_value = [zone_no_id]

        result = await service.get_all_zones()

        assert result == []
        # get_active_members should never be called for this zone
        zone_repo.get_active_members.assert_not_called()


class TestCreateZoneDbErrors:
    """Tests for create_zone DB persistence error cases."""

    @pytest.mark.asyncio
    async def test_continues_when_db_persist_fails(self):
        """Returns zone status even when DB persistence fails."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100")
        dev2 = _make_device("DEV002", "192.168.1.101")
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]
        device_repo.get_all.return_value = [dev1, dev2]

        mock_client = AsyncMock()
        mock_client.create_zone.return_value = _make_zone_status()
        zone_repo.create_zone.side_effect = Exception("DB write failed")

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.create_zone("DEV001", ["DEV002"])

        assert result.master_id == "DEV001"


class TestAddMembersConnectionError:
    """Tests for add_members error cases."""

    @pytest.mark.asyncio
    async def test_raises_connection_error_on_client_failure(self):
        """Raises DeviceConnectionError when add_zone_members fails."""
        service, device_repo, zone_repo = _make_service()
        dev1 = _make_device("DEV001")
        dev3 = _make_device("DEV003", "192.168.1.102")
        device_repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV003": dev3,
        }[did]

        mock_client = AsyncMock()
        mock_client.add_zone_members.side_effect = Exception("Timeout")

        with patch.object(service, "_get_client", return_value=mock_client):
            with pytest.raises(DeviceConnectionError):
                await service.add_members("DEV001", ["DEV003"])


class TestDissolveZoneEdgeCases:
    """Tests for dissolve_zone edge cases."""

    @pytest.mark.asyncio
    async def test_dissolve_no_zone_found_updates_db(self):
        """When no zone on device, still marks DB zone as dissolved."""
        from datetime import UTC, datetime

        from opencloudtouch.zones.repository import Zone

        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.return_value = _make_device()

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = None  # No zone

        zone_db = Zone(id=5, master_device_id="DEV001", created_at=datetime.now(UTC))
        zone_repo.get_active_zone_by_master.return_value = zone_db

        with patch.object(service, "_get_client", return_value=mock_client):
            await service.dissolve_zone("DEV001")

        zone_repo.dissolve_zone.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_dissolve_empty_members_updates_db(self):
        """When zone has empty members list, still marks DB zone as dissolved."""
        from datetime import UTC, datetime

        from opencloudtouch.zones.repository import Zone

        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.return_value = _make_device()

        mock_client = AsyncMock()
        # Zone exists but members is empty
        mock_client.get_zone_status.return_value = ZoneStatus(
            master_id="DEV001", master_ip="192.168.1.100", is_master=True, members=[]
        )

        zone_db = Zone(id=7, master_device_id="DEV001", created_at=datetime.now(UTC))
        zone_repo.get_active_zone_by_master.return_value = zone_db

        with patch.object(service, "_get_client", return_value=mock_client):
            await service.dissolve_zone("DEV001")

        zone_repo.dissolve_zone.assert_called_once_with(7)
        mock_client.remove_zone.assert_not_called()

    @pytest.mark.asyncio
    async def test_dissolve_updates_db_in_finally_block(self):
        """DB is updated even when remove_zone() raises exception."""
        from datetime import UTC, datetime

        from opencloudtouch.zones.repository import Zone

        service, device_repo, zone_repo = _make_service()
        device_repo.get_by_device_id.return_value = _make_device()

        zone_status = ZoneStatus(
            master_id="DEV001",
            master_ip="192.168.1.100",
            is_master=True,
            members=[
                ZoneMemberInfo(
                    device_id="DEV001", ip_address="192.168.1.100", role="master"
                ),
            ],
        )

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = zone_status
        mock_client.remove_zone.side_effect = Exception("Bose weirdness")

        zone_db = Zone(id=10, master_device_id="DEV001", created_at=datetime.now(UTC))
        zone_repo.get_active_zone_by_master.return_value = zone_db

        with patch.object(service, "_get_client", return_value=mock_client):
            await service.dissolve_zone("DEV001")

        # DB should still be updated despite exception
        zone_repo.dissolve_zone.assert_called_once_with(10)
