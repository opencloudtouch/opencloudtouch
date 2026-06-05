"""Unit tests for DeviceHealthCheck.

Tests the background health-check service that monitors device
reachability via HTTP ping and verifies setup status via SSH.
Focuses on:
- Lifecycle management (start/stop/cancellation)
- Device ping logic (reachable vs offline detection)
- SSH verification and status transitions
- Error resilience (network failures, SSH failures)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from opencloudtouch.devices.health_check import (
    OFFLINE_THRESHOLD,
    DeviceHealthCheck,
)
from opencloudtouch.devices.repository import Device


def _make_device(
    device_id: str = "dev1",
    ip: str = "192.168.1.100",
    name: str = "Living Room",
    last_seen: datetime | None = None,
    setup_status: str = "unknown",
    ssh_permanent: bool = False,
) -> Device:
    """Create a test device with sensible defaults."""
    return Device(
        device_id=device_id,
        ip=ip,
        name=name,
        model="SoundTouch 300",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="29.0.6",
        last_seen=last_seen or datetime.now(UTC),
        setup_status=setup_status,
        ssh_permanent=ssh_permanent,
    )


@pytest.fixture
def mock_repo():
    """Mock DeviceRepository with async methods."""
    repo = AsyncMock()
    repo.get_all.return_value = []
    return repo


@pytest.fixture
def health_check(mock_repo):
    """DeviceHealthCheck instance with mocked repository."""
    return DeviceHealthCheck(mock_repo)


class TestLifecycle:
    """Tests for start/stop behavior and task management."""

    def test_initial_state(self, health_check):
        """Health check starts in stopped state."""
        assert health_check._running is False
        assert health_check._task is None

    async def test_start_creates_task(self, health_check):
        """Starting creates a background asyncio task."""
        health_check.start()
        assert health_check._running is True
        assert health_check._task is not None
        await health_check.stop()

    async def test_start_is_idempotent(self, health_check):
        """Calling start() twice doesn't create a second task."""
        health_check.start()
        first_task = health_check._task
        health_check.start()
        assert health_check._task is first_task
        await health_check.stop()

    async def test_stop_cancels_task(self, health_check):
        """Stopping cancels the running task and cleans up."""
        health_check.start()
        assert health_check._task is not None

        await health_check.stop()

        assert health_check._running is False
        assert health_check._task is None

    async def test_stop_when_not_running_is_safe(self, health_check):
        """Stopping when not running doesn't raise."""
        await health_check.stop()
        assert health_check._task is None


class TestPingDevice:
    """Tests for individual device ping logic."""

    async def test_reachable_device_returns_true(self):
        """Device returning 200 on /info is considered reachable."""
        mock_client = AsyncMock()
        mock_resp = MagicMock(
            status_code=200, content=b"<info><name>Living Room</name></info>"
        )
        mock_client.get.return_value = mock_resp

        reachable, name = await DeviceHealthCheck._ping_device(
            mock_client, "192.168.1.100"
        )

        assert reachable is True
        assert name == "Living Room"
        mock_client.get.assert_called_once_with("http://192.168.1.100:8090/info")

    async def test_non_200_returns_false(self):
        """Device returning non-200 status is not reachable."""
        mock_client = AsyncMock()
        mock_client.get.return_value = MagicMock(status_code=500)

        reachable, name = await DeviceHealthCheck._ping_device(
            mock_client, "192.168.1.100"
        )

        assert reachable is False
        assert name is None

    async def test_connection_error_returns_false(self):
        """Connection error (device powered off) returns False."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        reachable, name = await DeviceHealthCheck._ping_device(
            mock_client, "192.168.1.100"
        )

        assert reachable is False
        assert name is None

    async def test_timeout_returns_false(self):
        """Timeout (device unreachable) returns False."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")

        reachable, name = await DeviceHealthCheck._ping_device(
            mock_client, "192.168.1.100"
        )

        assert reachable is False
        assert name is None

    async def test_malformed_xml_returns_true_without_name(self):
        """Malformed XML still reports device as reachable, name is None."""
        mock_client = AsyncMock()
        mock_resp = MagicMock(status_code=200, content=b"not xml at all")
        mock_client.get.return_value = mock_resp

        reachable, name = await DeviceHealthCheck._ping_device(
            mock_client, "192.168.1.100"
        )

        assert reachable is True
        assert name is None

    async def test_xml_without_name_element(self):
        """XML without <name> element returns None for name."""
        mock_client = AsyncMock()
        mock_resp = MagicMock(
            status_code=200, content=b"<info><type>ST300</type></info>"
        )
        mock_client.get.return_value = mock_resp

        reachable, name = await DeviceHealthCheck._ping_device(
            mock_client, "192.168.1.100"
        )

        assert reachable is True
        assert name is None


class TestPingAllDevices:
    """Tests for the batch ping logic that updates last_seen."""

    async def test_no_devices_does_nothing(self, health_check, mock_repo):
        """Empty device list doesn't cause errors."""
        mock_repo.get_all.return_value = []

        await health_check._ping_all_devices()

        mock_repo.upsert.assert_not_called()

    async def test_reachable_device_updates_last_seen(self, health_check, mock_repo):
        """Reachable device gets its last_seen timestamp updated."""
        device = _make_device(last_seen=datetime(2026, 1, 1, tzinfo=UTC))
        mock_repo.get_all.return_value = [device]

        with patch.object(DeviceHealthCheck, "_ping_device", return_value=(True, None)):
            await health_check._ping_all_devices()

        mock_repo.upsert.assert_called_once()
        updated_device = mock_repo.upsert.call_args[0][0]
        assert updated_device.last_seen > datetime(2026, 1, 1, tzinfo=UTC)

    async def test_unreachable_device_not_updated(self, health_check, mock_repo):
        """Unreachable device within threshold keeps its last_seen."""
        recent = datetime.now(UTC) - timedelta(seconds=60)
        device = _make_device(last_seen=recent)
        mock_repo.get_all.return_value = [device]

        with patch.object(
            DeviceHealthCheck, "_ping_device", return_value=(False, None)
        ):
            await health_check._ping_all_devices()

        mock_repo.upsert.assert_not_called()

    async def test_device_without_ip_is_skipped(self, health_check, mock_repo):
        """Device with no IP address is silently skipped."""
        device = _make_device(ip="")
        mock_repo.get_all.return_value = [device]

        with patch.object(
            DeviceHealthCheck, "_ping_device", return_value=(True, None)
        ) as mock_ping:
            await health_check._ping_all_devices()

        mock_ping.assert_not_called()

    async def test_offline_device_logs_warning(self, health_check, mock_repo):
        """Device exceeding offline threshold triggers a warning log."""
        old_time = datetime.now(UTC) - timedelta(seconds=OFFLINE_THRESHOLD + 60)
        device = _make_device(last_seen=old_time)
        mock_repo.get_all.return_value = [device]

        with (
            patch.object(DeviceHealthCheck, "_ping_device", return_value=(False, None)),
            patch("opencloudtouch.devices.health_check.logger") as mock_logger,
        ):
            await health_check._ping_all_devices()

        mock_logger.warning.assert_called_once()
        assert "offline" in mock_logger.warning.call_args[0][0].lower()

    async def test_name_change_updates_device(self, health_check, mock_repo):
        """Device name changed in Bose app gets synced to DB."""
        device = _make_device(name="Old Name")
        mock_repo.get_all.return_value = [device]

        with patch.object(
            DeviceHealthCheck, "_ping_device", return_value=(True, "New Name")
        ):
            await health_check._ping_all_devices()

        mock_repo.upsert.assert_called_once()
        updated_device = mock_repo.upsert.call_args[0][0]
        assert updated_device.name == "New Name"

    async def test_same_name_not_logged(self, health_check, mock_repo):
        """Device with unchanged name does not trigger name change log."""
        device = _make_device(name="Living Room")
        mock_repo.get_all.return_value = [device]

        with (
            patch.object(
                DeviceHealthCheck, "_ping_device", return_value=(True, "Living Room")
            ),
            patch("opencloudtouch.devices.health_check.logger") as mock_logger,
        ):
            await health_check._ping_all_devices()

        # info() should not be called for name change
        for call in mock_logger.info.call_args_list:
            assert "name changed" not in call[0][0].lower()

    async def test_none_name_preserves_existing(self, health_check, mock_repo):
        """If device name cannot be parsed, existing name is preserved."""
        device = _make_device(name="Original")
        mock_repo.get_all.return_value = [device]

        with patch.object(DeviceHealthCheck, "_ping_device", return_value=(True, None)):
            await health_check._ping_all_devices()

        mock_repo.upsert.assert_called_once()
        updated_device = mock_repo.upsert.call_args[0][0]
        assert updated_device.name == "Original"


class TestSSHVerification:
    """Tests for SSH-based setup status verification."""

    async def test_non_ssh_devices_skipped(self, health_check, mock_repo):
        """Devices without ssh_permanent=True are not SSH-checked."""
        device = _make_device(ssh_permanent=False)
        mock_repo.get_all.return_value = [device]

        with patch("opencloudtouch.devices.health_check.check_ssh_port") as mock_ssh:
            await health_check._ssh_verify_all()

        mock_ssh.assert_not_called()

    async def test_ssh_unreachable_skips_verification(self, health_check, mock_repo):
        """If SSH port is closed, skip further verification."""
        device = _make_device(ssh_permanent=True)
        mock_repo.get_all.return_value = [device]

        with patch(
            "opencloudtouch.devices.health_check.check_ssh_port",
            return_value=False,
        ):
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        mock_repo.update_setup_status.assert_not_called()

    async def test_ssh_unreachable_does_not_reset_on_first_cycle(
        self, health_check, mock_repo
    ):
        """Single SSH failure must NOT reset ssh_permanent (grace period)."""
        device = _make_device(
            ssh_permanent=True, setup_status="configured", device_id="dev-grace"
        )

        with patch(
            "opencloudtouch.devices.health_check.check_ssh_port",
            return_value=False,
        ):
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        # After only 1 failure, ssh_permanent must NOT be reset
        mock_repo.update_setup_status.assert_not_called()

    async def test_ssh_unreachable_consecutive_resets_ssh_permanent(
        self, health_check, mock_repo
    ):
        """2 consecutive SSH failures must reset ssh_permanent=False."""
        device = _make_device(
            ssh_permanent=True, setup_status="configured", device_id="dev-reset"
        )

        with patch(
            "opencloudtouch.devices.health_check.check_ssh_port",
            return_value=False,
        ):
            # First failure — grace period
            await health_check._ssh_verify_device(device, "http://myserver:7777")
            # Second failure — should trigger reset
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        mock_repo.update_setup_status.assert_called_once_with(
            device_id="dev-reset",
            setup_status="configured",
            ssh_permanent=False,
        )

    async def test_ssh_reachable_resets_fail_count(self, health_check, mock_repo):
        """After failures, a successful SSH check resets the counter."""
        device = _make_device(
            ssh_permanent=True, setup_status="configured", device_id="dev-recover"
        )

        mock_conn = MagicMock(success=True)
        mock_client = AsyncMock()
        mock_client.connect.return_value = mock_conn
        mock_client.execute.side_effect = [
            MagicMock(output="bmxRegistryUrl=http://myserver:7777/bmx"),
            MagicMock(output="0"),
        ]
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.devices.health_check.check_ssh_port",
            return_value=False,
        ):
            # Accumulate 1 failure
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        # Now SSH comes back
        with (
            patch(
                "opencloudtouch.devices.health_check.check_ssh_port",
                return_value=True,
            ),
            patch(
                "opencloudtouch.devices.health_check.SoundTouchSSHClient",
                return_value=mock_client,
            ),
        ):
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        # After recovery, another single failure must NOT reset
        # (counter was cleared by success)
        mock_repo.update_setup_status.reset_mock()
        with patch(
            "opencloudtouch.devices.health_check.check_ssh_port",
            return_value=False,
        ):
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        mock_repo.update_setup_status.assert_not_called()

    async def test_ssh_fail_count_per_device_isolation(self, health_check, mock_repo):
        """Failure tracking is per-device — device A failures don't affect B."""
        device_a = _make_device(
            ssh_permanent=True, setup_status="configured", device_id="dev-A"
        )
        device_b = _make_device(
            ssh_permanent=True, setup_status="configured", device_id="dev-B"
        )

        with patch(
            "opencloudtouch.devices.health_check.check_ssh_port",
            return_value=False,
        ):
            # Device A: 1 failure
            await health_check._ssh_verify_device(device_a, "http://myserver:7777")
            # Device B: 1 failure
            await health_check._ssh_verify_device(device_b, "http://myserver:7777")
            # Device A: 2nd failure — should trigger reset for A only
            await health_check._ssh_verify_device(device_a, "http://myserver:7777")

        # Only device A should have been reset (2 consecutive)
        calls = mock_repo.update_setup_status.call_args_list
        assert len(calls) == 1
        assert calls[0].kwargs["device_id"] == "dev-A"
        assert calls[0].kwargs["ssh_permanent"] is False

    async def test_configured_status_when_our_server_in_bmx(
        self, health_check, mock_repo
    ):
        """Device with our server URL in BMX config → 'configured'."""
        device = _make_device(ssh_permanent=True, setup_status="unconfigured")
        mock_repo.get_all.return_value = [device]

        mock_conn = MagicMock(success=True)
        mock_client = AsyncMock()
        mock_client.connect.return_value = mock_conn
        mock_client.execute.side_effect = [
            MagicMock(output="bmxRegistryUrl=http://myserver:7777/bmx"),
            MagicMock(output="0"),  # no hosts redirect
        ]
        mock_client.close = AsyncMock()

        with (
            patch(
                "opencloudtouch.devices.health_check.check_ssh_port",
                return_value=True,
            ),
            patch(
                "opencloudtouch.devices.health_check.SoundTouchSSHClient",
                return_value=mock_client,
            ),
        ):
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        mock_repo.update_setup_status.assert_called_once_with(
            device_id="dev1", setup_status="configured"
        )

    async def test_unconfigured_status_when_bose_url(self, health_check, mock_repo):
        """Device still pointing to bose.com → 'unconfigured'."""
        device = _make_device(ssh_permanent=True, setup_status="configured")

        mock_conn = MagicMock(success=True)
        mock_client = AsyncMock()
        mock_client.connect.return_value = mock_conn
        mock_client.execute.side_effect = [
            MagicMock(output="bmxRegistryUrl=https://streaming.bose.com/bmx"),
            MagicMock(output="0"),
        ]
        mock_client.close = AsyncMock()

        with (
            patch(
                "opencloudtouch.devices.health_check.check_ssh_port",
                return_value=True,
            ),
            patch(
                "opencloudtouch.devices.health_check.SoundTouchSSHClient",
                return_value=mock_client,
            ),
        ):
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        mock_repo.update_setup_status.assert_called_once_with(
            device_id="dev1", setup_status="unconfigured"
        )

    async def test_hosts_redirect_means_configured(self, health_check, mock_repo):
        """Hosts file redirect (Strategy B) → 'configured'."""
        device = _make_device(ssh_permanent=True, setup_status="unconfigured")

        mock_conn = MagicMock(success=True)
        mock_client = AsyncMock()
        mock_client.connect.return_value = mock_conn
        mock_client.execute.side_effect = [
            MagicMock(output="bmxRegistryUrl=https://streaming.bose.com/bmx"),
            MagicMock(output="1"),  # hosts redirect present
        ]
        mock_client.close = AsyncMock()

        with (
            patch(
                "opencloudtouch.devices.health_check.check_ssh_port",
                return_value=True,
            ),
            patch(
                "opencloudtouch.devices.health_check.SoundTouchSSHClient",
                return_value=mock_client,
            ),
        ):
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        mock_repo.update_setup_status.assert_called_once_with(
            device_id="dev1", setup_status="configured"
        )

    async def test_no_status_change_skips_update(self, health_check, mock_repo):
        """If status hasn't changed, don't call update."""
        device = _make_device(ssh_permanent=True, setup_status="configured")

        mock_conn = MagicMock(success=True)
        mock_client = AsyncMock()
        mock_client.connect.return_value = mock_conn
        mock_client.execute.side_effect = [
            MagicMock(output="bmxRegistryUrl=http://myserver:7777/bmx"),
            MagicMock(output="0"),
        ]
        mock_client.close = AsyncMock()

        with (
            patch(
                "opencloudtouch.devices.health_check.check_ssh_port",
                return_value=True,
            ),
            patch(
                "opencloudtouch.devices.health_check.SoundTouchSSHClient",
                return_value=mock_client,
            ),
        ):
            await health_check._ssh_verify_device(device, "http://myserver:7777")

        mock_repo.update_setup_status.assert_not_called()

    async def test_ssh_failure_doesnt_crash(self, health_check, mock_repo):
        """SSH exception in verify_all doesn't crash the health check."""
        device = _make_device(ssh_permanent=True)
        mock_repo.get_all.return_value = [device]

        with patch.object(
            health_check, "_ssh_verify_device", side_effect=Exception("SSH boom")
        ):
            # Should not raise
            await health_check._ssh_verify_all()


class TestZoneSyncAll:
    """Tests for _zone_sync_all() — zone drift detection and resolution."""

    @pytest.fixture
    def mock_zone_repo(self):
        """Mock ZoneRepository with async methods."""
        return AsyncMock()

    @pytest.fixture
    def zone_health_check(self, mock_repo, mock_zone_repo):
        """DeviceHealthCheck with both device and zone repos."""
        return DeviceHealthCheck(mock_repo, zone_repo=mock_zone_repo)

    def _make_zone(
        self,
        zone_id: int = 1,
        master_device_id: str = "dev1",
    ):
        """Create a Zone entity for testing."""
        from datetime import UTC, datetime

        from opencloudtouch.zones.repository import Zone

        return Zone(
            id=zone_id,
            master_device_id=master_device_id,
            created_at=datetime.now(UTC),
        )

    def _make_zone_member(
        self,
        zone_id: int = 1,
        device_id: str = "dev1",
        role: str = "master",
    ):
        """Create a ZoneMember entity for testing."""
        from datetime import UTC, datetime

        from opencloudtouch.zones.repository import ZoneMember

        return ZoneMember(
            zone_id=zone_id,
            device_id=device_id,
            role=role,
            added_at=datetime.now(UTC),
        )

    def _make_zone_status(self, master_id="dev1", members=None):
        """Create a ZoneStatus from the adapter layer."""
        from opencloudtouch.zones.models import ZoneMemberInfo, ZoneStatus

        if members is None:
            members = [
                ZoneMemberInfo(
                    device_id="dev1", ip_address="192.168.1.100", role="master"
                ),
                ZoneMemberInfo(
                    device_id="dev2", ip_address="192.168.1.101", role="slave"
                ),
            ]
        return ZoneStatus(
            master_id=master_id,
            master_ip="192.168.1.100",
            is_master=True,
            members=members,
        )

    async def test_no_zone_repo_returns_early(self, mock_repo):
        """Without zone_repo injected, _zone_sync_all is a no-op."""
        hc = DeviceHealthCheck(mock_repo, zone_repo=None)
        await hc._zone_sync_all()
        # No exception, no calls — just returns

    async def test_no_active_zones_returns_early(
        self, zone_health_check, mock_zone_repo
    ):
        """No active zones in DB → nothing to sync."""
        mock_zone_repo.get_all_active_zones.return_value = []

        await zone_health_check._zone_sync_all()

        mock_zone_repo.dissolve_zone.assert_not_called()
        mock_zone_repo.add_member.assert_not_called()
        mock_zone_repo.remove_member.assert_not_called()

    async def test_zone_with_none_id_is_skipped(
        self, zone_health_check, mock_zone_repo
    ):
        """Zone from DB with id=None is skipped with error log."""
        zone = self._make_zone(zone_id=None)
        mock_zone_repo.get_all_active_zones.return_value = [zone]

        with patch("opencloudtouch.devices.health_check.logger") as mock_logger:
            await zone_health_check._zone_sync_all()

        mock_logger.error.assert_called_once()
        assert "no ID" in mock_logger.error.call_args[0][0]

    async def test_master_not_found_skips_zone(
        self, zone_health_check, mock_repo, mock_zone_repo
    ):
        """Master device not in DB → skip this zone."""
        zone = self._make_zone()
        mock_zone_repo.get_all_active_zones.return_value = [zone]
        mock_repo.get_by_device_id.return_value = None

        await zone_health_check._zone_sync_all()

        mock_zone_repo.dissolve_zone.assert_not_called()

    async def test_master_without_ip_skips_zone(
        self, zone_health_check, mock_repo, mock_zone_repo
    ):
        """Master device has no IP → skip this zone."""
        zone = self._make_zone()
        mock_zone_repo.get_all_active_zones.return_value = [zone]
        mock_repo.get_by_device_id.return_value = _make_device(ip="")

        await zone_health_check._zone_sync_all()

        mock_zone_repo.dissolve_zone.assert_not_called()

    async def test_device_reports_no_zone_dissolves_in_db(
        self, zone_health_check, mock_repo, mock_zone_repo
    ):
        """Device reports no zone → dissolve_zone() is called."""
        zone = self._make_zone(zone_id=42)
        mock_zone_repo.get_all_active_zones.return_value = [zone]
        mock_repo.get_by_device_id.return_value = _make_device()

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = None

        with patch(
            "opencloudtouch.devices.adapter.get_device_client",
            return_value=mock_client,
        ):
            await zone_health_check._zone_sync_all()

        mock_zone_repo.dissolve_zone.assert_called_once_with(42)

    async def test_members_match_no_update(
        self, zone_health_check, mock_repo, mock_zone_repo
    ):
        """DB members match device members → no add/remove calls."""
        zone = self._make_zone(zone_id=1)
        mock_zone_repo.get_all_active_zones.return_value = [zone]
        mock_repo.get_by_device_id.return_value = _make_device()

        # DB has dev1 (master) + dev2 (slave)
        mock_zone_repo.get_active_members.return_value = [
            self._make_zone_member(zone_id=1, device_id="dev1", role="master"),
            self._make_zone_member(zone_id=1, device_id="dev2", role="slave"),
        ]

        # Device also reports dev1 + dev2
        from opencloudtouch.zones.models import ZoneMemberInfo

        status = self._make_zone_status(
            members=[
                ZoneMemberInfo(
                    device_id="dev1", ip_address="192.168.1.100", role="master"
                ),
                ZoneMemberInfo(
                    device_id="dev2", ip_address="192.168.1.101", role="slave"
                ),
            ]
        )

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = status

        with patch(
            "opencloudtouch.devices.adapter.get_device_client",
            return_value=mock_client,
        ):
            await zone_health_check._zone_sync_all()

        mock_zone_repo.add_member.assert_not_called()
        mock_zone_repo.remove_member.assert_not_called()
        mock_zone_repo.dissolve_zone.assert_not_called()

    async def test_device_has_extra_member_adds_to_db(
        self, zone_health_check, mock_repo, mock_zone_repo
    ):
        """Device has member not in DB → add_member() called."""
        zone = self._make_zone(zone_id=5)
        mock_zone_repo.get_all_active_zones.return_value = [zone]
        mock_repo.get_by_device_id.return_value = _make_device()

        # DB only has dev1
        mock_zone_repo.get_active_members.return_value = [
            self._make_zone_member(zone_id=5, device_id="dev1", role="master"),
        ]

        # Device has dev1 + dev3 (new member)
        from opencloudtouch.zones.models import ZoneMemberInfo

        status = self._make_zone_status(
            members=[
                ZoneMemberInfo(
                    device_id="dev1", ip_address="192.168.1.100", role="master"
                ),
                ZoneMemberInfo(
                    device_id="dev3", ip_address="192.168.1.102", role="slave"
                ),
            ]
        )

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = status

        with patch(
            "opencloudtouch.devices.adapter.get_device_client",
            return_value=mock_client,
        ):
            await zone_health_check._zone_sync_all()

        mock_zone_repo.add_member.assert_called_once_with(5, "dev3", "slave")
        mock_zone_repo.remove_member.assert_not_called()

    async def test_db_has_extra_member_removes_from_db(
        self, zone_health_check, mock_repo, mock_zone_repo
    ):
        """DB has member not on device → remove_member() called."""
        zone = self._make_zone(zone_id=7)
        mock_zone_repo.get_all_active_zones.return_value = [zone]
        mock_repo.get_by_device_id.return_value = _make_device()

        # DB has dev1 + dev2
        mock_zone_repo.get_active_members.return_value = [
            self._make_zone_member(zone_id=7, device_id="dev1", role="master"),
            self._make_zone_member(zone_id=7, device_id="dev2", role="slave"),
        ]

        # Device only has dev1 (dev2 left)
        from opencloudtouch.zones.models import ZoneMemberInfo

        status = self._make_zone_status(
            members=[
                ZoneMemberInfo(
                    device_id="dev1", ip_address="192.168.1.100", role="master"
                ),
            ]
        )

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = status

        with patch(
            "opencloudtouch.devices.adapter.get_device_client",
            return_value=mock_client,
        ):
            await zone_health_check._zone_sync_all()

        mock_zone_repo.remove_member.assert_called_once_with(7, "dev2")
        mock_zone_repo.add_member.assert_not_called()

    async def test_drift_both_added_and_removed(
        self, zone_health_check, mock_repo, mock_zone_repo
    ):
        """Members added AND removed simultaneously → both operations."""
        zone = self._make_zone(zone_id=3)
        mock_zone_repo.get_all_active_zones.return_value = [zone]
        mock_repo.get_by_device_id.return_value = _make_device()

        # DB has dev1 + dev2
        mock_zone_repo.get_active_members.return_value = [
            self._make_zone_member(zone_id=3, device_id="dev1", role="master"),
            self._make_zone_member(zone_id=3, device_id="dev2", role="slave"),
        ]

        # Device has dev1 + dev4 (dev2 removed, dev4 added)
        from opencloudtouch.zones.models import ZoneMemberInfo

        status = self._make_zone_status(
            members=[
                ZoneMemberInfo(
                    device_id="dev1", ip_address="192.168.1.100", role="master"
                ),
                ZoneMemberInfo(
                    device_id="dev4", ip_address="192.168.1.103", role="slave"
                ),
            ]
        )

        mock_client = AsyncMock()
        mock_client.get_zone_status.return_value = status

        with patch(
            "opencloudtouch.devices.adapter.get_device_client",
            return_value=mock_client,
        ):
            await zone_health_check._zone_sync_all()

        mock_zone_repo.add_member.assert_called_once_with(3, "dev4", "slave")
        mock_zone_repo.remove_member.assert_called_once_with(3, "dev2")

    async def test_get_zone_status_exception_continues(
        self, zone_health_check, mock_repo, mock_zone_repo
    ):
        """Exception during get_zone_status → logged, continues to next zone."""
        zone1 = self._make_zone(zone_id=1, master_device_id="devA")
        zone2 = self._make_zone(zone_id=2, master_device_id="devB")
        mock_zone_repo.get_all_active_zones.return_value = [zone1, zone2]

        devA = _make_device(device_id="devA", ip="192.168.1.10")
        devB = _make_device(device_id="devB", ip="192.168.1.11")
        mock_repo.get_by_device_id.side_effect = lambda did: {
            "devA": devA,
            "devB": devB,
        }.get(did)

        # First client throws, second returns no zone
        mock_client_a = AsyncMock()
        mock_client_a.get_zone_status.side_effect = Exception("Connection refused")
        mock_client_b = AsyncMock()
        mock_client_b.get_zone_status.return_value = None

        def fake_get_client(url):
            if "192.168.1.10" in url:
                return mock_client_a
            return mock_client_b

        with patch(
            "opencloudtouch.devices.adapter.get_device_client",
            side_effect=fake_get_client,
        ):
            await zone_health_check._zone_sync_all()

        # Zone 2 should still be dissolved despite zone 1 failing
        mock_zone_repo.dissolve_zone.assert_called_once_with(2)

    async def test_outer_exception_caught_and_logged(
        self, zone_health_check, mock_zone_repo
    ):
        """Fatal exception in the outer try → logged, doesn't crash."""
        mock_zone_repo.get_all_active_zones.side_effect = RuntimeError("DB gone")

        with patch("opencloudtouch.devices.health_check.logger") as mock_logger:
            await zone_health_check._zone_sync_all()

        mock_logger.exception.assert_called_once()
        assert "cycle failed" in mock_logger.exception.call_args[0][0]

    async def test_multiple_zones_processed(
        self, zone_health_check, mock_repo, mock_zone_repo
    ):
        """All zones from DB are iterated and checked."""
        zones = [
            self._make_zone(zone_id=i, master_device_id=f"dev{i}") for i in range(1, 4)
        ]
        mock_zone_repo.get_all_active_zones.return_value = zones

        # All masters found but no IPs → all skipped
        for z in zones:
            mock_repo.get_by_device_id.return_value = _make_device(ip="")

        await zone_health_check._zone_sync_all()

        # Nothing dissolved/added/removed since all skipped (no IP)
        mock_zone_repo.dissolve_zone.assert_not_called()
        mock_zone_repo.add_member.assert_not_called()
        mock_zone_repo.remove_member.assert_not_called()


class TestHealthCheckRunLoop:
    """Tests for the _run loop, especially CancelledError propagation."""

    async def test_cancelled_error_propagates_from_run_loop(self, mock_repo):
        """CancelledError in _run must re-raise (not be swallowed)."""
        import asyncio

        hc = DeviceHealthCheck(mock_repo)
        mock_repo.get_all.return_value = []

        # Start the health check and then cancel it
        hc.start()
        assert hc._task is not None

        # Cancel and verify clean shutdown
        hc._task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await hc._task
