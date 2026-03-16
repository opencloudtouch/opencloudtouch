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
    """Create ZoneService with mocked repo."""
    repo = AsyncMock()
    return ZoneService(device_repo=repo), repo


class TestGetZoneStatus:
    """Tests for get_zone_status."""

    @pytest.mark.asyncio
    async def test_returns_zone_status(self):
        """Returns enriched zone status for a device."""
        service, repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100", "Living Room")
        dev2 = _make_device("DEV002", "192.168.1.101", "Kitchen")
        repo.get_by_device_id.return_value = dev1
        repo.get_all.return_value = [dev1, dev2]

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
        service, repo = _make_service()
        repo.get_by_device_id.return_value = _make_device()

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = None

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.get_zone_status("DEV001")

        assert result is None

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_device(self):
        """Raises DeviceNotFoundError for unknown device ID."""
        service, repo = _make_service()
        repo.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await service.get_zone_status("UNKNOWN")


class TestGetAllZones:
    """Tests for get_all_zones."""

    @pytest.mark.asyncio
    async def test_returns_all_zones(self):
        """Returns deduplicated zones across devices."""
        service, repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100")
        dev2 = _make_device("DEV002", "192.168.1.101")
        repo.get_all.return_value = [dev1, dev2]

        zone = _make_zone_status()
        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = zone

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.get_all_zones()

        # Both devices see same zone (same master_id) → deduplicated to 1
        assert len(result) == 1
        assert result[0].master_id == "DEV001"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_devices(self):
        """Returns empty list when no devices exist."""
        service, repo = _make_service()
        repo.get_all.return_value = []

        result = await service.get_all_zones()
        assert result == []

    @pytest.mark.asyncio
    async def test_skips_unreachable_devices(self):
        """Skips devices that fail and returns zones from reachable ones."""
        service, repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100")
        dev2 = _make_device("DEV002", "192.168.1.101")
        repo.get_all.return_value = [dev1, dev2]

        zone = _make_zone_status(
            "DEV002",
            "192.168.1.101",
            [
                ZoneMemberInfo(
                    device_id="DEV002", ip_address="192.168.1.101", role="master"
                ),
            ],
        )

        client_ok = AsyncMock()
        client_ok.get_zone_status.return_value = zone
        client_fail = AsyncMock()
        client_fail.get_zone_status.side_effect = Exception("Timeout")

        def get_client(ip):
            if "100" in ip:
                return client_fail
            return client_ok

        with patch.object(service, "_get_client", side_effect=get_client):
            result = await service.get_all_zones()

        assert len(result) == 1
        assert result[0].master_id == "DEV002"

    @pytest.mark.asyncio
    async def test_prefers_master_perspective_over_slave(self):
        """Uses master's zone status which has the complete member list."""
        service, repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100", "Speaker 1")
        dev2 = _make_device("DEV002", "192.168.1.101", "Speaker 2")
        dev3 = _make_device("DEV003", "192.168.1.102", "Speaker 3")
        repo.get_all.return_value = [dev1, dev2, dev3]

        # Slave perspective: incomplete members (only 2)
        slave_zone = ZoneStatus(
            master_id="DEV001",
            master_ip="192.168.1.100",
            is_master=False,
            members=[
                ZoneMemberInfo(
                    device_id="DEV001", ip_address="192.168.1.100", role="master"
                ),
                ZoneMemberInfo(
                    device_id="DEV002", ip_address="192.168.1.101", role="slave"
                ),
            ],
        )
        # Master perspective: complete members (all 3)
        master_zone = ZoneStatus(
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

        def get_client(ip):
            client = AsyncMock()
            if "100" in ip:
                client.get_zone_status.return_value = master_zone
            elif "101" in ip:
                client.get_zone_status.return_value = slave_zone
            else:
                client.get_zone_status.return_value = slave_zone
            return client

        with patch.object(service, "_get_client", side_effect=get_client):
            result = await service.get_all_zones()

        assert len(result) == 1
        assert len(result[0].members) == 3

    @pytest.mark.asyncio
    async def test_five_device_zone_all_members_returned(self):
        """Zone with 5 devices returns all 5 enriched members."""
        service, repo = _make_service()
        devices = [
            _make_device(f"DEV{i:03d}", f"192.168.1.{100+i}", f"Speaker {i}")
            for i in range(5)
        ]
        repo.get_all.return_value = devices

        all_members = [
            ZoneMemberInfo(
                device_id=f"DEV{i:03d}",
                ip_address=f"192.168.1.{100+i}",
                role="master" if i == 0 else "slave",
            )
            for i in range(5)
        ]
        zone = ZoneStatus(
            master_id="DEV000",
            master_ip="192.168.1.100",
            is_master=True,
            members=all_members,
        )

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = zone

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.get_all_zones()

        assert len(result) == 1
        assert len(result[0].members) == 5
        assert result[0].members[0].name == "Speaker 0"
        assert result[0].members[4].name == "Speaker 4"


class TestCreateZone:
    """Tests for create_zone."""

    @pytest.mark.asyncio
    async def test_creates_zone_successfully(self):
        """Creates zone and returns enriched status."""
        service, repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100", "Living Room")
        dev2 = _make_device("DEV002", "192.168.1.101", "Kitchen")
        repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]
        repo.get_all.return_value = [dev1, dev2]

        mock_client = AsyncMock()
        mock_client.create_zone.return_value = _make_zone_status()

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.create_zone("DEV001", ["DEV002"])

        assert result.master_id == "DEV001"
        assert len(result.members) == 2

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_master(self):
        """Raises DeviceNotFoundError when master not found."""
        service, repo = _make_service()
        repo.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await service.create_zone("UNKNOWN", ["DEV002"])

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_slave(self):
        """Raises DeviceNotFoundError when a slave is not found."""
        service, repo = _make_service()
        master = _make_device("DEV001")
        repo.get_by_device_id.side_effect = lambda did: (
            master if did == "DEV001" else None
        )

        with pytest.raises(DeviceNotFoundError):
            await service.create_zone("DEV001", ["UNKNOWN"])

    @pytest.mark.asyncio
    async def test_raises_connection_error_on_failure(self):
        """Raises DeviceConnectionError when creation fails."""
        service, repo = _make_service()
        dev1 = _make_device("DEV001")
        dev2 = _make_device("DEV002", "192.168.1.101")
        repo.get_by_device_id.side_effect = lambda did: {
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
        service, repo = _make_service()
        dev1 = _make_device("DEV001")
        dev3 = _make_device("DEV003", "192.168.1.102")
        repo.get_by_device_id.side_effect = lambda did: {
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
        service, repo = _make_service()
        repo.get_by_device_id.side_effect = lambda did: (
            _make_device() if did == "DEV001" else None
        )

        with pytest.raises(DeviceNotFoundError):
            await service.add_members("DEV001", ["UNKNOWN"])


class TestRemoveMembers:
    """Tests for remove_members."""

    @pytest.mark.asyncio
    async def test_removes_members_successfully(self):
        """Removes members from zone without error."""
        service, repo = _make_service()
        dev1 = _make_device("DEV001")
        dev2 = _make_device("DEV002", "192.168.1.101")
        repo.get_by_device_id.side_effect = lambda did: {
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
        service, repo = _make_service()
        dev1 = _make_device("DEV001")
        dev2 = _make_device("DEV002", "192.168.1.101")
        repo.get_by_device_id.side_effect = lambda did: {
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
        """Dissolves zone without error."""
        service, repo = _make_service()
        repo.get_by_device_id.return_value = _make_device()

        mock_client = AsyncMock()
        with patch.object(service, "_get_client", return_value=mock_client):
            await service.dissolve_zone("DEV001")

        mock_client.remove_zone.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_device(self):
        """Raises DeviceNotFoundError for unknown master."""
        service, repo = _make_service()
        repo.get_by_device_id.return_value = None

        with pytest.raises(DeviceNotFoundError):
            await service.dissolve_zone("UNKNOWN")


class TestChangeMaster:
    """Tests for change_master."""

    @pytest.mark.asyncio
    async def test_changes_master_successfully(self):
        """Dissolves old zone and creates new one with new master."""
        service, repo = _make_service()
        dev1 = _make_device("DEV001", "192.168.1.100", "Living Room")
        dev2 = _make_device("DEV002", "192.168.1.101", "Kitchen")
        repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]
        repo.get_all.return_value = [dev1, dev2]

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
        service, repo = _make_service()
        dev1 = _make_device("DEV001")
        dev2 = _make_device("DEV002", "192.168.1.101")
        repo.get_by_device_id.side_effect = lambda did: {
            "DEV001": dev1,
            "DEV002": dev2,
        }[did]

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = None

        with patch.object(service, "_get_client", return_value=mock_client):
            with pytest.raises(ValueError, match="not in a zone"):
                await service.change_master("DEV001", "DEV002")
