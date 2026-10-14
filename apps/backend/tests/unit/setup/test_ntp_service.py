"""
Unit tests for SoundTouchNtpService.

Covers issue #469 acceptance criteria:
- Writes the chosen server to /etc/ntpservers.txt and syncs via ntpd
- Remounts read-only even if the write is cancelled mid-flight
- Backs up the original file once, so it can be restored
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.setup.ntp_service import SoundTouchNtpService
from opencloudtouch.setup.ssh_client import CommandResult


def _ok(output: str = "") -> CommandResult:
    """Helper: successful CommandResult."""
    return CommandResult(success=True, output=output, exit_code=0)


def _fail(error: str = "error") -> CommandResult:
    """Helper: failed CommandResult."""
    return CommandResult(success=False, output="", exit_code=1, error=error)


@pytest.fixture
def mock_ssh():
    """Mocked SoundTouchSSHClient."""
    ssh = MagicMock()
    ssh.execute = AsyncMock()
    return ssh


@pytest.fixture
def service(mock_ssh):
    return SoundTouchNtpService(mock_ssh)


class TestPatchNtp:
    """patch_ntp() writes /etc/ntpservers.txt and triggers an ntpd sync."""

    @pytest.mark.asyncio
    async def test_writes_ntp_servers_file(self, service, mock_ssh):
        """patch_ntp must write the server to /etc/ntpservers.txt."""
        mock_ssh.execute.return_value = _ok()

        await service.patch_ntp("ntp.example.local")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        write_calls = [
            cmd
            for cmd in calls
            if "/etc/ntpservers.txt" in cmd
            and any(x in cmd for x in ["echo", "base64", ">", "mv", "tee"])
        ]
        assert len(write_calls) >= 1, (
            f"patch_ntp must write to /etc/ntpservers.txt. SSH calls were: {calls}"
        )

    @pytest.mark.asyncio
    async def test_chosen_server_is_listed_first(self, service, mock_ssh):
        """The user-chosen server must appear first in the diff / written content."""
        mock_ssh.execute.return_value = _ok()

        result = await service.patch_ntp("ntp.example.local")

        assert result.success is True
        assert result.diff.strip().splitlines()[0].endswith("ntp.example.local")

    @pytest.mark.asyncio
    async def test_triggers_ntpd_resync(self, service, mock_ssh):
        """patch_ntp must run ntpd once against the new server to sync immediately."""
        mock_ssh.execute.return_value = _ok()

        await service.patch_ntp("ntp.example.local")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        ntpd_calls = [c for c in calls if "ntpd" in c and "ntp.example.local" in c]
        assert len(ntpd_calls) >= 1, f"No ntpd resync call found. SSH calls: {calls}"

    @pytest.mark.asyncio
    async def test_remounts_rw_before_write(self, service, mock_ssh):
        """Filesystem must be remounted read-write before writing."""
        mock_ssh.execute.return_value = _ok()

        await service.patch_ntp("ntp.example.local")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        assert any("remount,rw" in c for c in calls)

    @pytest.mark.asyncio
    async def test_remounts_ro_after_write(self, service, mock_ssh):
        """Filesystem must be remounted read-only after writing."""
        mock_ssh.execute.return_value = _ok()

        await service.patch_ntp("ntp.example.local")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        assert any("remount,ro" in c for c in calls)

    @pytest.mark.asyncio
    async def test_remounts_ro_even_if_write_is_cancelled(self, service, mock_ssh):
        """A cancelled write must still remount read-only (issue #469 acceptance criterion)."""

        async def side_effect(cmd, **kwargs):
            if "/etc/ntpservers.txt" in cmd and "base64" in cmd:
                raise asyncio.CancelledError()
            return _ok()

        mock_ssh.execute = AsyncMock(side_effect=side_effect)

        with pytest.raises(asyncio.CancelledError):
            await service.patch_ntp("ntp.example.local")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        assert any("remount,ro" in c for c in calls), (
            "Root filesystem must be remounted read-only even when the write is "
            "cancelled mid-flight — otherwise it stays writable indefinitely."
        )

    @pytest.mark.asyncio
    async def test_reports_backup_path(self, service, mock_ssh):
        """patch_ntp must report where the pre-patch backup was created."""
        mock_ssh.execute.return_value = _ok()

        result = await service.patch_ntp("ntp.example.local")

        assert result.success is True
        assert result.backup_path != ""

    @pytest.mark.asyncio
    async def test_handles_write_failure(self, service, mock_ssh):
        """If the write command fails, patch_ntp must return success=False."""

        async def side_effect(cmd, **kwargs):
            if "/etc/ntpservers.txt" in cmd and "base64" in cmd:
                return _fail("Permission denied")
            return _ok()

        mock_ssh.execute = AsyncMock(side_effect=side_effect)

        result = await service.patch_ntp("ntp.example.local")

        assert result.success is False

    @pytest.mark.asyncio
    async def test_handles_ntpd_sync_failure(self, service, mock_ssh):
        """If ntpd fails to sync, patch_ntp must return success=False."""

        async def side_effect(cmd, **kwargs):
            if "ntpd" in cmd:
                return _fail("no route to host")
            return _ok()

        mock_ssh.execute = AsyncMock(side_effect=side_effect)

        result = await service.patch_ntp("ntp.example.local")

        assert result.success is False


class TestRestoreNtp:
    """restore_ntp() reverts /etc/ntpservers.txt from the pre-patch backup."""

    @pytest.mark.asyncio
    async def test_restore_success(self, service, mock_ssh):
        """Successful restore copies backup to /etc/ntpservers.txt."""
        mock_ssh.execute.return_value = _ok("exists")

        result = await service.restore_ntp("/mnt/nv/ntpservers_backup")

        assert result.success is True
        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        cp_calls = [c for c in calls if "cp" in c and "/etc/ntpservers.txt" in c]
        assert len(cp_calls) >= 1

    @pytest.mark.asyncio
    async def test_restore_backup_not_found(self, service, mock_ssh):
        """Restore fails gracefully when no backup exists."""
        mock_ssh.execute.return_value = _ok("missing")

        result = await service.restore_ntp("/mnt/nv/ntpservers_backup")

        assert result.success is False
        assert "not found" in (result.error or "").lower()
