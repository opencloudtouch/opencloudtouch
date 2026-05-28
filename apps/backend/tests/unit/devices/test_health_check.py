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
        mock_client.get.return_value = MagicMock(status_code=200)

        result = await DeviceHealthCheck._ping_device(mock_client, "192.168.1.100")

        assert result is True
        mock_client.get.assert_called_once_with("http://192.168.1.100:8090/info")

    async def test_non_200_returns_false(self):
        """Device returning non-200 status is not reachable."""
        mock_client = AsyncMock()
        mock_client.get.return_value = MagicMock(status_code=500)

        result = await DeviceHealthCheck._ping_device(mock_client, "192.168.1.100")

        assert result is False

    async def test_connection_error_returns_false(self):
        """Connection error (device powered off) returns False."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        result = await DeviceHealthCheck._ping_device(mock_client, "192.168.1.100")

        assert result is False

    async def test_timeout_returns_false(self):
        """Timeout (device unreachable) returns False."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")

        result = await DeviceHealthCheck._ping_device(mock_client, "192.168.1.100")

        assert result is False


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

        with patch.object(DeviceHealthCheck, "_ping_device", return_value=True):
            await health_check._ping_all_devices()

        mock_repo.upsert.assert_called_once()
        updated_device = mock_repo.upsert.call_args[0][0]
        assert updated_device.last_seen > datetime(2026, 1, 1, tzinfo=UTC)

    async def test_unreachable_device_not_updated(self, health_check, mock_repo):
        """Unreachable device within threshold keeps its last_seen."""
        recent = datetime.now(UTC) - timedelta(seconds=60)
        device = _make_device(last_seen=recent)
        mock_repo.get_all.return_value = [device]

        with patch.object(DeviceHealthCheck, "_ping_device", return_value=False):
            await health_check._ping_all_devices()

        mock_repo.upsert.assert_not_called()

    async def test_device_without_ip_is_skipped(self, health_check, mock_repo):
        """Device with no IP address is silently skipped."""
        device = _make_device(ip="")
        mock_repo.get_all.return_value = [device]

        with patch.object(
            DeviceHealthCheck, "_ping_device", return_value=True
        ) as mock_ping:
            await health_check._ping_all_devices()

        mock_ping.assert_not_called()

    async def test_offline_device_logs_warning(self, health_check, mock_repo):
        """Device exceeding offline threshold triggers a warning log."""
        old_time = datetime.now(UTC) - timedelta(seconds=OFFLINE_THRESHOLD + 60)
        device = _make_device(last_seen=old_time)
        mock_repo.get_all.return_value = [device]

        with (
            patch.object(DeviceHealthCheck, "_ping_device", return_value=False),
            patch("opencloudtouch.devices.health_check.logger") as mock_logger,
        ):
            await health_check._ping_all_devices()

        mock_logger.warning.assert_called_once()
        assert "offline" in mock_logger.warning.call_args[0][0].lower()


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
