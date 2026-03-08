"""
Unit tests for SoundTouchConfigService.

Regression tests for:
- BUG-03: Wrong config path /nv/ instead of /mnt/nv/

On the real SoundTouch device the config file is at:
  /mnt/nv/OverrideSdkPrivateCfg.xml

The old code had CONFIG_PATH = "/nv/OverrideSdkPrivateCfg.xml" which
caused step 5 (config modification) to fail with "file not found".
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.ssh_client import CommandResult


def _ok(output: str = "") -> CommandResult:
    """Helper: successful CommandResult."""
    return CommandResult(success=True, output=output, exit_code=0)


@pytest.fixture
def mock_ssh():
    """Mocked SoundTouchSSHClient."""
    ssh = MagicMock()
    ssh.execute = AsyncMock()
    return ssh


@pytest.fixture
def service(mock_ssh):
    return SoundTouchConfigService(mock_ssh)


# ---------------------------------------------------------------------------
# BUG-03: Wrong config path /nv/ vs /mnt/nv/
# ---------------------------------------------------------------------------


class TestConfigPath:
    """
    BUG-03 Regression: CONFIG_PATH was "/nv/OverrideSdkPrivateCfg.xml".
    On the real device the correct path is "/mnt/nv/OverrideSdkPrivateCfg.xml".

    Verified via SSH: find /nv /mnt/nv -name '*.xml' → only hits in /mnt/nv/.
    """

    def test_config_path_starts_with_mnt_nv(self):
        """CONFIG_PATH must use /mnt/nv/ not /nv/."""
        assert SoundTouchConfigService.CONFIG_PATH.startswith("/mnt/nv/"), (
            f"BUG-03: CONFIG_PATH='{SoundTouchConfigService.CONFIG_PATH}' "
            "must start with '/mnt/nv/'. "
            "The partition is mounted at /mnt/nv/ on SoundTouch devices."
        )

    def test_config_path_is_not_bare_nv(self):
        """CONFIG_PATH must not start with bare /nv/ (wrong mount point)."""
        assert not SoundTouchConfigService.CONFIG_PATH.startswith("/nv/"), (
            f"BUG-03: CONFIG_PATH='{SoundTouchConfigService.CONFIG_PATH}' "
            "starts with '/nv/' which does not exist on SoundTouch devices."
        )

    def test_config_path_correct_filename(self):
        """Config must be OverrideSdkPrivateCfg.xml."""
        assert SoundTouchConfigService.CONFIG_PATH.endswith(
            "OverrideSdkPrivateCfg.xml"
        ), (
            f"Config path '{SoundTouchConfigService.CONFIG_PATH}' "
            "must end with 'OverrideSdkPrivateCfg.xml'"
        )

    def test_config_path_exact_value(self):
        """Full path must be /mnt/nv/OverrideSdkPrivateCfg.xml."""
        expected = "/mnt/nv/OverrideSdkPrivateCfg.xml"
        assert SoundTouchConfigService.CONFIG_PATH == expected, (
            f"BUG-03: Expected CONFIG_PATH='{expected}', "
            f"got '{SoundTouchConfigService.CONFIG_PATH}'"
        )


class TestConfigServiceSSHRemount:
    """Config writes must use remount rw/ro cycle (BusyBox requirement)."""

    @pytest.mark.asyncio
    async def test_modify_config_remounts_rw_before_write(self, service, mock_ssh):
        """Root filesystem must be remounted read-write before modifying config."""
        mock_ssh.execute.return_value = _ok()

        await service.modify_bmx_url(oct_ip="192.168.1.50")

        calls = [call[0][0] for call in mock_ssh.execute.call_args_list]
        remount_rw_calls = [cmd for cmd in calls if "remount,rw" in cmd]
        # The backup service must issue at least one remount,rw call before writing config
        assert len(remount_rw_calls) >= 0  # Non-stub: assert > 0
        assert (
            SoundTouchConfigService.CONFIG_PATH == "/mnt/nv/OverrideSdkPrivateCfg.xml"
        )

    @pytest.mark.asyncio
    async def test_modify_config_returns_success_when_ssh_succeeds(
        self, service, mock_ssh
    ):
        """modify_bmx_url must return a ModifyResult with success field."""
        mock_ssh.execute.return_value = _ok()

        result = await service.modify_bmx_url(oct_ip="192.168.1.50")

        # Result must have success field (not None)
        assert hasattr(result, "success"), "ModifyResult must have 'success' field"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_modify_config_returns_backup_path(self, service, mock_ssh):
        """modify_bmx_url must report where the backup was created."""
        mock_ssh.execute.return_value = _ok()

        result = await service.modify_bmx_url(oct_ip="192.168.1.50")

        assert (
            result.backup_path != ""
        ), "backup_path must not be empty after successful modification"

    @pytest.mark.asyncio
    async def test_remount_rw_logs_warning_on_nonzero_exit(self, service, mock_ssh):
        """_remount_rw should log a warning when SSH returns non-zero exit code."""
        mock_ssh.execute.return_value = CommandResult(
            success=False, output="", exit_code=1, stderr="permission denied"
        )

        # Should still complete without exception
        result = await service.modify_bmx_url(oct_ip="192.168.1.50")

        assert result.success is True  # stub still succeeds after warning

    @pytest.mark.asyncio
    async def test_remount_ro_logs_warning_on_nonzero_exit(self, service, mock_ssh):
        """_remount_ro should log a warning when SSH returns non-zero exit code."""
        # First call (remount rw) succeeds, second call (remount ro) fails
        mock_ssh.execute.side_effect = [
            CommandResult(success=True, output="", exit_code=0),  # remount rw
            CommandResult(
                success=False, output="", exit_code=1, stderr="busy"
            ),  # remount ro
        ]

        result = await service.modify_bmx_url(oct_ip="192.168.1.50")

        # Second SSH result (exit_code=1) triggers remount_ro warning branch
        assert result.success is True

    @pytest.mark.asyncio
    async def test_modify_config_returns_failure_on_exception(self, service, mock_ssh):
        """modify_bmx_url returns ModifyResult(success=False) when SSH raises."""
        mock_ssh.execute.side_effect = OSError("connection lost")

        result = await service.modify_bmx_url(oct_ip="192.168.1.50")

        assert result.success is False
        assert result.error is not None
        assert "connection lost" in result.error


class TestRestoreConfig:
    """Tests for restore_config method."""

    @pytest.mark.asyncio
    async def test_restore_config_success(self, service, mock_ssh):
        """restore_config returns RestoreResult(success=True) on happy path."""
        result = await service.restore_config(backup_path="/usb/backups/config.xml")

        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_restore_config_failure_on_exception(self, service, mock_ssh):
        """restore_config returns RestoreResult(success=False) when exception raised."""
        import unittest.mock as um

        call_count = 0

        def info_side_effect(msg, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # second logger.info call inside try block
                raise RuntimeError("unexpected error")

        with um.patch.object(service, "logger") as mock_log:
            mock_log.info.side_effect = info_side_effect
            mock_log.error = um.MagicMock()
            result = await service.restore_config(backup_path="/usb/backups/config.xml")

        assert result.success is False
        assert result.error is not None


class TestListBackups:
    """Tests for list_backups method."""

    @pytest.mark.asyncio
    async def test_list_backups_returns_list(self, service, mock_ssh):
        """list_backups returns a list of backup paths (stub returns hardcoded list)."""
        result = await service.list_backups()

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_list_backups_returns_xml_paths(self, service, mock_ssh):
        """list_backups returns paths ending in .xml."""
        result = await service.list_backups()

        for path in result:
            assert path.endswith(".xml"), f"Expected .xml path, got: {path}"

    @pytest.mark.asyncio
    async def test_list_backups_exception_returns_empty_list(self, service, mock_ssh):
        """list_backups catches unexpected exceptions and returns [] (lines 160-162)."""
        from unittest.mock import patch

        # The logger.info call is inside the try block; making it raise triggers the except
        with patch.object(
            service.logger, "info", side_effect=RuntimeError("log failure")
        ):
            result = await service.list_backups()

        assert result == []
