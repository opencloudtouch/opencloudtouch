"""Unit tests for BoseDeviceClientAdapter zone methods."""

from unittest.mock import MagicMock, patch

import pytest

from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.client_adapter import BoseDeviceClientAdapter
from opencloudtouch.zones.models import ZoneMemberInfo, ZoneStatus


def _make_client(base_url: str = "http://192.168.1.100:8090"):
    """Create BoseDeviceClientAdapter with mocked BoseClient."""
    with patch("opencloudtouch.devices.client_adapter.SoundTouchDevice"), patch(
        "opencloudtouch.devices.client_adapter.BoseClient"
    ):
        return BoseDeviceClientAdapter(base_url)


def _make_mock_zone(
    master_id="DEV001", master_ip="192.168.1.100", members=None, is_master=True
):
    """Create a mock bosesoundtouchapi Zone object."""
    zone = MagicMock()
    zone.MasterDeviceId = master_id
    zone.MasterIpAddress = master_ip
    zone.IsZoneMaster = is_master
    if members is None:
        m1 = MagicMock()
        m1.DeviceId = master_id
        m1.IpAddress = master_ip
        m2 = MagicMock()
        m2.DeviceId = "DEV002"
        m2.IpAddress = "192.168.1.101"
        zone.Members = [m1, m2]
    else:
        zone.Members = members
    return zone


class TestGetZoneStatus:
    """Tests for get_zone_status."""

    @pytest.mark.asyncio
    async def test_returns_zone_status(self):
        """Returns ZoneStatus when device is in a zone."""
        client = _make_client()
        zone = _make_mock_zone()
        client._client.GetZoneStatus.return_value = zone

        result = await client.get_zone_status()

        assert isinstance(result, ZoneStatus)
        assert result.master_id == "DEV001"
        assert result.is_master is True
        assert len(result.members) == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_no_zone(self):
        """Returns None when device is not in a zone."""
        client = _make_client()
        zone = MagicMock()
        zone.MasterDeviceId = None
        client._client.GetZoneStatus.return_value = zone

        result = await client.get_zone_status()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self):
        """Returns None when client fails (device offline)."""
        client = _make_client()
        client._client.GetZoneStatus.side_effect = Exception("Connection refused")

        result = await client.get_zone_status()
        assert result is None

    @pytest.mark.asyncio
    async def test_members_have_correct_roles(self):
        """Master member has role 'master', others have 'slave'."""
        client = _make_client()
        zone = _make_mock_zone()
        client._client.GetZoneStatus.return_value = zone

        result = await client.get_zone_status()
        roles = {m.device_id: m.role for m in result.members}
        assert roles["DEV001"] == "master"
        assert roles["DEV002"] == "slave"


class TestCreateZone:
    """Tests for create_zone."""

    @pytest.mark.asyncio
    async def test_creates_zone_successfully(self):
        """Creates zone and returns status."""
        client = _make_client()
        client._client.Device.DeviceId = "DEV001"
        zone = _make_mock_zone()
        client._client.GetZoneStatus.return_value = zone

        members = [
            ZoneMemberInfo(device_id="DEV002", ip_address="192.168.1.101", role="slave")
        ]
        result = await client.create_zone("192.168.1.100", members)

        assert isinstance(result, ZoneStatus)
        client._client.CreateZone.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_connection_error_on_failure(self):
        """Raises DeviceConnectionError when create fails."""
        client = _make_client()
        client._client.Device.DeviceId = "DEV001"
        client._client.CreateZone.side_effect = Exception("Timeout")

        members = [
            ZoneMemberInfo(device_id="DEV002", ip_address="192.168.1.101", role="slave")
        ]
        with pytest.raises(DeviceConnectionError):
            await client.create_zone("192.168.1.100", members)


class TestAddZoneMembers:
    """Tests for add_zone_members."""

    @pytest.mark.asyncio
    async def test_adds_members_successfully(self):
        """Calls AddZoneMembers on underlying client."""
        client = _make_client()
        members = [
            ZoneMemberInfo(device_id="DEV003", ip_address="192.168.1.102", role="slave")
        ]

        await client.add_zone_members(members)
        client._client.AddZoneMembers.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_connection_error_on_failure(self):
        """Raises DeviceConnectionError when add fails."""
        client = _make_client()
        client._client.AddZoneMembers.side_effect = Exception("Error")

        members = [
            ZoneMemberInfo(device_id="DEV003", ip_address="192.168.1.102", role="slave")
        ]
        with pytest.raises(DeviceConnectionError):
            await client.add_zone_members(members)


class TestRemoveZoneMembers:
    """Tests for remove_zone_members."""

    @pytest.mark.asyncio
    async def test_removes_members_successfully(self):
        """Calls RemoveZoneMembers on underlying client."""
        client = _make_client()
        members = [
            ZoneMemberInfo(device_id="DEV002", ip_address="192.168.1.101", role="slave")
        ]

        await client.remove_zone_members(members)
        client._client.RemoveZoneMembers.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_connection_error_on_failure(self):
        """Raises DeviceConnectionError when remove fails."""
        client = _make_client()
        client._client.RemoveZoneMembers.side_effect = Exception("Error")

        members = [
            ZoneMemberInfo(device_id="DEV002", ip_address="192.168.1.101", role="slave")
        ]
        with pytest.raises(DeviceConnectionError):
            await client.remove_zone_members(members)


class TestRemoveZone:
    """Tests for remove_zone."""

    @pytest.mark.asyncio
    async def test_removes_zone_successfully(self):
        """Calls RemoveZone on underlying client."""
        client = _make_client()

        await client.remove_zone()
        client._client.RemoveZone.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_connection_error_on_failure(self):
        """Raises DeviceConnectionError when remove fails."""
        client = _make_client()
        client._client.RemoveZone.side_effect = Exception("Error")

        with pytest.raises(DeviceConnectionError):
            await client.remove_zone()


class TestZoneToStatusMasterInjection:
    """Tests for _zone_to_status master injection with many devices."""

    @pytest.mark.asyncio
    async def test_injects_master_when_missing_from_members(self):
        """Master is injected into members when API omits it."""
        client = _make_client()
        # Zone where API only returns slaves, master missing from members
        members = []
        for i in range(4):
            m = MagicMock()
            m.DeviceId = f"SLAVE{i+1:03d}"
            m.IpAddress = f"192.168.1.{i+10}"
            members.append(m)
        zone = _make_mock_zone(
            master_id="MASTER01",
            master_ip="192.168.1.1",
            members=members,
            is_master=True,
        )
        client._client.GetZoneStatus.return_value = zone

        result = await client.get_zone_status()

        assert result is not None
        assert len(result.members) == 5  # 4 slaves + injected master
        assert result.members[0].device_id == "MASTER01"
        assert result.members[0].role == "master"

    @pytest.mark.asyncio
    async def test_five_device_zone_all_members_present(self):
        """Zone with 5 devices returns all 5 members with correct roles."""
        client = _make_client()
        members = []
        # Master
        m = MagicMock()
        m.DeviceId = "MASTER01"
        m.IpAddress = "192.168.1.1"
        members.append(m)
        # 4 slaves
        for i in range(4):
            m = MagicMock()
            m.DeviceId = f"SLAVE{i+1:03d}"
            m.IpAddress = f"192.168.1.{i+10}"
            members.append(m)
        zone = _make_mock_zone(
            master_id="MASTER01",
            master_ip="192.168.1.1",
            members=members,
            is_master=True,
        )
        client._client.GetZoneStatus.return_value = zone

        result = await client.get_zone_status()

        assert result is not None
        assert len(result.members) == 5
        roles = {m.device_id: m.role for m in result.members}
        assert roles["MASTER01"] == "master"
        for i in range(4):
            assert roles[f"SLAVE{i+1:03d}"] == "slave"

    @pytest.mark.asyncio
    async def test_no_duplicate_master_when_already_present(self):
        """Master is NOT duplicated when API already includes it."""
        client = _make_client()
        zone = _make_mock_zone()  # default: master + 1 slave
        client._client.GetZoneStatus.return_value = zone

        result = await client.get_zone_status()

        assert result is not None
        assert len(result.members) == 2
        master_count = sum(1 for m in result.members if m.role == "master")
        assert master_count == 1
