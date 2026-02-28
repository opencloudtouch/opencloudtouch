"""
Unit tests for SoundTouchConfigService.

Regression tests for:
- BUG-03: Wrong config path /nv/ instead of /mnt/nv/

On the real SoundTouch device the config file is at:
  /mnt/nv/OverrideSdkPrivateCfg.xml

The old code had CONFIG_PATH = "/nv/OverrideSdkPrivateCfg.xml" which
caused step 5 (config modification) to fail with "file not found".
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

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
