"""
Unit tests for SoundTouchBackupService.

Covers:
- USB mount point detection
- Per-volume tar command routing
- Real size/duration reporting
- Graceful failure when archive is empty
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.setup.backup_service import SoundTouchBackupService, VolumeType
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
    return SoundTouchBackupService(mock_ssh)


# ---------------------------------------------------------------------------
# _find_usb_mount
# ---------------------------------------------------------------------------


class TestFindUsbMount:
    async def test_returns_detected_mount(self, service, mock_ssh):
        mock_ssh.execute.return_value = _ok("/media/sda1")

        result = await service._find_usb_mount()

        assert result == "/media/sda1"
        mock_ssh.execute.assert_awaited_once()

    async def test_falls_back_when_grep_empty(self, service, mock_ssh):
        mock_ssh.execute.return_value = _ok("")

        result = await service._find_usb_mount()

        assert result == "/media/sda1"

    async def test_falls_back_when_command_fails(self, service, mock_ssh):
        mock_ssh.execute.return_value = _fail("permission denied")

        result = await service._find_usb_mount()

        assert result == "/media/sda1"

    async def test_strips_trailing_whitespace(self, service, mock_ssh):
        mock_ssh.execute.return_value = _ok("/media/usb  \n")

        result = await service._find_usb_mount()

        assert result == "/media/usb"


# ---------------------------------------------------------------------------
# _backup_volume
# ---------------------------------------------------------------------------


class TestBackupVolume:
    async def test_rootfs_uses_correct_tar_command(self, service, mock_ssh):
        backup_dir = "/media/sda1/oct-backup"
        expected_file = f"{backup_dir}/soundtouch-rootfs.tgz"

        mock_ssh.execute.side_effect = [
            _ok(),  # tar command
            _ok("61341696"),  # wc -c (size)
        ]

        await service._backup_volume(VolumeType.ROOTFS, backup_dir)

        tar_call = mock_ssh.execute.await_args_list[0]
        cmd = tar_call[0][0]
        assert "tar czf" in cmd
        assert expected_file in cmd
        assert "bin boot etc home lib mnt opt sbin srv usr var" in cmd

    async def test_persistent_uses_mnt_nv(self, service, mock_ssh):
        backup_dir = "/media/sda1/oct-backup"
        mock_ssh.execute.side_effect = [_ok(), _ok("10240")]

        await service._backup_volume(VolumeType.PERSISTENT, backup_dir)

        cmd = mock_ssh.execute.await_args_list[0][0][0]
        assert "/mnt/nv" in cmd
        assert "soundtouch-nv.tgz" in cmd

    async def test_update_uses_mnt_update(self, service, mock_ssh):
        backup_dir = "/media/sda1/oct-backup"
        mock_ssh.execute.side_effect = [_ok(), _ok("954966")]

        await service._backup_volume(VolumeType.UPDATE, backup_dir)

        cmd = mock_ssh.execute.await_args_list[0][0][0]
        assert "/mnt/update" in cmd
        assert "soundtouch-update.tgz" in cmd

    async def test_returns_real_size_from_wc(self, service, mock_ssh):
        mock_ssh.execute.side_effect = [_ok(), _ok("61341696")]

        result = await service._backup_volume(
            VolumeType.ROOTFS, "/media/sda1/oct-backup"
        )

        assert result.success is True
        assert result.size_bytes == 61341696
        assert result.size_bytes / 1024 / 1024 == pytest.approx(58.5, abs=1.0)

    async def test_fails_when_archive_empty(self, service, mock_ssh):
        """tar exit 1 + zero-byte file → failure (distinguishes from BusyBox tar warnings)."""
        mock_ssh.execute.side_effect = [
            _fail("some tar warning"),  # tar returned non-zero
            _ok("0"),  # wc -c = 0 bytes
        ]

        result = await service._backup_volume(
            VolumeType.ROOTFS, "/media/sda1/oct-backup"
        )

        assert result.success is False
        assert result.size_bytes == 0
        assert result.error is not None

    async def test_succeeds_despite_tar_exit1_if_archive_written(
        self, service, mock_ssh
    ):
        """BusyBox tar often exits 1 for socket files — success if bytes > 0."""
        mock_ssh.execute.side_effect = [
            _fail("tar: Removing leading slash"),  # non-zero exit
            _ok("59400000"),  # but archive exists
        ]

        result = await service._backup_volume(
            VolumeType.ROOTFS, "/media/sda1/oct-backup"
        )

        assert result.success is True
        assert result.size_bytes == 59400000

    async def test_duration_is_measured(self, service, mock_ssh):
        mock_ssh.execute.side_effect = [_ok(), _ok("61341696")]

        result = await service._backup_volume(
            VolumeType.ROOTFS, "/media/sda1/oct-backup"
        )

        assert result.duration_seconds >= 0.0


# ---------------------------------------------------------------------------
# backup_all
# ---------------------------------------------------------------------------


class TestBackupAll:
    async def test_backs_up_three_volumes(self, service, mock_ssh):
        # find_usb_mount + mkdir + (tar + wc) × 3
        mock_ssh.execute.side_effect = [
            _ok("/media/sda1"),  # find_usb_mount
            _ok(),  # mkdir
            _ok(),
            _ok("61341696"),  # rootfs
            _ok(),
            _ok("10240"),  # persistent
            _ok(),
            _ok("954966"),  # update
        ]

        results = await service.backup_all()

        assert len(results) == 3
        volumes = [r.volume for r in results]
        assert VolumeType.ROOTFS in volumes
        assert VolumeType.PERSISTENT in volumes
        assert VolumeType.UPDATE in volumes

    async def test_all_volumes_succeed(self, service, mock_ssh):
        mock_ssh.execute.side_effect = [
            _ok("/media/sda1"),
            _ok(),
            _ok(),
            _ok("61341696"),
            _ok(),
            _ok("10240"),
            _ok(),
            _ok("954966"),
        ]

        results = await service.backup_all()

        assert all(r.success for r in results)

    async def test_continues_after_single_volume_failure(self, service, mock_ssh):
        """If rootfs fails, persistent and update should still be attempted."""
        mock_ssh.execute.side_effect = [
            _ok("/media/sda1"),
            _ok(),
            _fail("No space left"),
            _ok("0"),  # rootfs fails
            _ok(),
            _ok("10240"),  # persistent succeeds
            _ok(),
            _ok("954966"),  # update succeeds
        ]

        results = await service.backup_all()

        assert len(results) == 3
        assert results[0].success is False  # rootfs
        assert results[1].success is True  # persistent
        assert results[2].success is True  # update

    async def test_backup_dir_uses_oct_backup_subdirectory(self, service, mock_ssh):
        mock_ssh.execute.side_effect = [
            _ok("/media/sda1"),
            _ok(),
            _ok(),
            _ok("61341696"),
            _ok(),
            _ok("10240"),
            _ok(),
            _ok("954966"),
        ]

        await service.backup_all()

        mkdir_call = mock_ssh.execute.await_args_list[1]
        assert "oct-backup" in mkdir_call[0][0]
        assert "/media/sda1/oct-backup" in mkdir_call[0][0]

    async def test_exception_in_volume_captured_as_failure(self, service, mock_ssh):
        """RuntimeError during backup → BackupResult(success=False)."""
        find_and_mkdir = [_ok("/media/sda1"), _ok()]
        mock_ssh.execute.side_effect = find_and_mkdir + [Exception("SSH disconnected")]

        results = await service.backup_all()

        rootfs_result = next(r for r in results if r.volume == VolumeType.ROOTFS)
        assert rootfs_result.success is False
        assert "SSH disconnected" in (rootfs_result.error or "")

    async def test_mkdir_failure_logs_warning_but_continues(self, service, mock_ssh):
        """backup_all logs a warning when mkdir -p fails but continues (line 104).

        mkdir failure is non-fatal: the backup dir may already exist.
        """
        mock_ssh.execute.side_effect = [
            _ok("/media/sda1"),  # find_usb_mount
            _fail("mkdir: /media/sda1/oct-backup: File exists"),  # mkdir fails
            _ok(),  # tar rootfs
            _ok("61341696"),  # wc -c rootfs
            _ok(),  # tar persistent
            _ok("10240"),  # wc -c persistent
            _ok(),  # tar update
            _ok("954966"),  # wc -c update
        ]

        results = await service.backup_all()

        # Should still attempt all volumes despite mkdir warning
        assert len(results) == 3
