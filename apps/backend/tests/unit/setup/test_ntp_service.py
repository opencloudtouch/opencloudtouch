"""
Unit tests for SoundTouchNtpService.

Covers issue #469 acceptance criteria:
- Writes the chosen server to /etc/ntpservers.txt and syncs via ntpd
- Remounts read-only even if the write is cancelled mid-flight
- Backs up the original file once, so it can be restored
"""

import asyncio
import shlex
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
        assert (
            len(write_calls) >= 1
        ), f"patch_ntp must write to /etc/ntpservers.txt. SSH calls were: {calls}"

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
    async def test_ntpd_argument_is_shell_quoted(self, service, mock_ssh):
        """The server name is interpolated into the ntpd command line, so shell
        metacharacters must be neutralised even though the API validates input."""
        mock_ssh.execute.return_value = _ok()
        hostile = "ntp.example.local; reboot"

        await service.patch_ntp(hostile)

        ntpd_cmd = next(
            c[0][0] for c in mock_ssh.execute.call_args_list if "ntpd" in c[0][0]
        )
        assert shlex.quote(hostile) in ntpd_cmd
        assert f"-p {hostile}" not in ntpd_cmd

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
    async def test_ntpd_sync_failure_does_not_fail_the_patch(self, service, mock_ssh):
        """ntpd is best-effort: a failed resync must not be reported as a failed
        patch, since the file was already written (PR #504 review finding)."""

        async def side_effect(cmd, **kwargs):
            if "ntpd" in cmd:
                return _fail("no route to host")
            return _ok()

        mock_ssh.execute = AsyncMock(side_effect=side_effect)

        result = await service.patch_ntp("ntp.example.local")

        assert result.success is True
        assert result.synced is False

    @pytest.mark.asyncio
    async def test_synced_is_true_on_successful_resync(self, service, mock_ssh):
        """synced reflects the immediate resync outcome, separate from success."""
        mock_ssh.execute.return_value = _ok()

        result = await service.patch_ntp("ntp.example.local")

        assert result.synced is True

    @pytest.mark.asyncio
    async def test_ntpd_call_uses_bounded_timeout(self, service, mock_ssh):
        """The resync call must not use the generic unbounded SSH default —
        a short timeout keeps it from blocking the whole patch request."""
        mock_ssh.execute.return_value = _ok()

        await service.patch_ntp("ntp.example.local")

        ntpd_call = next(
            c for c in mock_ssh.execute.call_args_list if "ntpd" in c[0][0]
        )
        assert ntpd_call.kwargs.get("timeout") == service.NTPD_RESYNC_TIMEOUT

    @pytest.mark.asyncio
    async def test_handles_backup_failure(self, service, mock_ssh):
        """If the pre-patch backup can't be created, abort before overwriting
        the original file — unlike /etc/hosts, the backup is the only way back."""

        async def side_effect(cmd, **kwargs):
            if cmd.startswith("test -f"):
                return _ok("missing")
            if cmd.startswith("cp "):
                return _fail("Permission denied")
            return _ok()

        mock_ssh.execute = AsyncMock(side_effect=side_effect)

        result = await service.patch_ntp("ntp.example.local")

        assert result.success is False
        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        write_calls = [c for c in calls if "base64" in c]
        assert not write_calls, "Must not write the new file when the backup failed"

    @pytest.mark.asyncio
    async def test_does_not_overwrite_an_existing_backup(self, service, mock_ssh):
        """_ensure_backup must preserve the first-ever backup, not refresh it."""
        mock_ssh.execute.return_value = _ok("exists")

        await service.patch_ntp("ntp.example.local")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        cp_calls = [c for c in calls if c.startswith("cp ")]
        assert not cp_calls, "Backup must not be re-copied once it already exists"

    @pytest.mark.asyncio
    async def test_diff_lists_chosen_and_fallback_servers(self, service, mock_ssh):
        """diff must describe the real written content, not just the chosen server."""
        mock_ssh.execute.return_value = _ok()

        result = await service.patch_ntp("ntp.example.local")

        for server in ["ntp.example.local", *service.FALLBACK_SERVERS]:
            assert server in result.diff

    @pytest.mark.asyncio
    async def test_written_payload_decodes_to_servers_in_order(self, service, mock_ssh):
        """The base64 payload actually sent to the device must contain the
        chosen server first, followed by the fallback servers."""
        import base64

        mock_ssh.execute.return_value = _ok()

        await service.patch_ntp("ntp.example.local")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        write_cmd = next(c for c in calls if "base64 -d" in c)
        b64_payload = write_cmd.split("'")[1]
        decoded = base64.b64decode(b64_payload).decode()
        assert decoded == "ntp.example.local\n0.pool.ntp.org\n1.pool.ntp.org\n"
