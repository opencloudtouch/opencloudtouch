"""Unit tests for RestoreService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.setup.restore_models import (
    BackupFileInfo,
    BackupSet,
    RestoreResult,
    RestoreStep,
    RestoreStepName,
    StepStatus,
    ValidationStatus,
)
from opencloudtouch.setup.restore_service import RestoreService


class TestRestoreModels:
    """Smoke tests to verify restore models are importable and constructible."""

    def test_backup_file_info_defaults(self):
        info = BackupFileInfo(
            filename="soundtouch-ABC123-20250512-rootfs.tgz",
            volume_type="rootfs",
            file_path="/media/sda1/oct-backup/soundtouch-ABC123-20250512-rootfs.tgz",
        )
        assert info.device_id is None
        assert info.is_pre_restore is False
        assert info.validation_status == ValidationStatus.VALID

    def test_backup_set_defaults(self):
        bs = BackupSet()
        assert bs.files == []
        assert bs.is_legacy is False
        assert bs.is_match is False

    def test_restore_step_defaults(self):
        step = RestoreStep(name=RestoreStepName.CONFIG)
        assert step.status == StepStatus.PENDING
        assert step.duration_seconds == 0.0

    def test_restore_result_defaults(self):
        result = RestoreResult()
        assert result.success is False
        assert result.restore_type == "clean"
        assert result.steps == []


class TestParseBackupFilename:
    """T010: Tests for _parse_backup_filename()."""

    def test_modern_filename_rootfs(self):
        info = RestoreService._parse_backup_filename(
            "soundtouch-ABC123DEF456-20250512-rootfs.tgz"
        )
        assert info.device_id == "ABC123DEF456"
        assert info.backup_date == "20250512"
        assert info.volume_type == "rootfs"
        assert info.is_pre_restore is False

    def test_modern_filename_nv(self):
        info = RestoreService._parse_backup_filename(
            "soundtouch-ABC123DEF456-20250512-nv.tgz"
        )
        assert info.device_id == "ABC123DEF456"
        assert info.backup_date == "20250512"
        assert info.volume_type == "persistent"

    def test_modern_filename_update(self):
        info = RestoreService._parse_backup_filename(
            "soundtouch-ABC123DEF456-20250512-update.tgz"
        )
        assert info.device_id == "ABC123DEF456"
        assert info.volume_type == "update"

    def test_legacy_filename_rootfs(self):
        info = RestoreService._parse_backup_filename("soundtouch-rootfs.tgz")
        assert info.device_id is None
        assert info.backup_date is None
        assert info.volume_type == "rootfs"

    def test_legacy_filename_nv(self):
        info = RestoreService._parse_backup_filename("soundtouch-nv.tgz")
        assert info.volume_type == "persistent"
        assert info.device_id is None

    def test_pre_restore_detected(self):
        info = RestoreService._parse_backup_filename(
            "soundtouch-ABC123DEF456-20250512-pre-restore-rootfs.tgz"
        )
        assert info.is_pre_restore is True
        assert info.volume_type == "rootfs"

    def test_unknown_filename_returns_none(self):
        info = RestoreService._parse_backup_filename("random-file.txt")
        assert info is None


class TestSelectBackupSet:
    """T016: Tests for _select_backup_set()."""

    def test_exact_device_id_match(self):
        from opencloudtouch.setup.restore_models import BackupFileInfo, BackupSet

        sets = [
            BackupSet(
                device_id="ABC123",
                backup_date="20250512",
                files=[
                    BackupFileInfo(
                        filename="soundtouch-ABC123-20250512-rootfs.tgz",
                        volume_type="rootfs",
                        file_path="/media/sda1/oct-backup/soundtouch-ABC123-20250512-rootfs.tgz",
                        device_id="ABC123",
                        backup_date="20250512",
                    )
                ],
            ),
            BackupSet(
                device_id="OTHER789",
                backup_date="20250101",
                files=[
                    BackupFileInfo(
                        filename="soundtouch-OTHER789-20250101-rootfs.tgz",
                        volume_type="rootfs",
                        file_path="/media/sda1/oct-backup/soundtouch-OTHER789-20250101-rootfs.tgz",
                        device_id="OTHER789",
                    )
                ],
            ),
        ]
        selected = RestoreService._select_backup_set(sets, "ABC123")
        assert selected is not None
        assert selected.device_id == "ABC123"
        assert selected.is_match is True

    def test_legacy_fallback(self):
        from opencloudtouch.setup.restore_models import BackupFileInfo, BackupSet

        sets = [
            BackupSet(
                device_id=None,
                is_legacy=True,
                files=[
                    BackupFileInfo(
                        filename="soundtouch-rootfs.tgz",
                        volume_type="rootfs",
                        file_path="/media/sda1/oct-backup/soundtouch-rootfs.tgz",
                    )
                ],
            ),
        ]
        selected = RestoreService._select_backup_set(sets, "ABC123")
        assert selected is not None
        assert selected.is_legacy is True

    def test_no_match_returns_none(self):
        from opencloudtouch.setup.restore_models import BackupFileInfo, BackupSet

        sets = [
            BackupSet(
                device_id="OTHER789",
                files=[
                    BackupFileInfo(
                        filename="soundtouch-OTHER789-20250101-rootfs.tgz",
                        volume_type="rootfs",
                        file_path="/media/sda1/oct-backup/soundtouch-OTHER789-20250101-rootfs.tgz",
                        device_id="OTHER789",
                    )
                ],
            ),
        ]
        selected = RestoreService._select_backup_set(sets, "ABC123")
        assert selected is None

    def test_newest_date_preferred(self):
        from opencloudtouch.setup.restore_models import BackupFileInfo, BackupSet

        sets = [
            BackupSet(
                device_id="ABC123",
                backup_date="20250101",
                files=[
                    BackupFileInfo(
                        filename="soundtouch-ABC123-20250101-rootfs.tgz",
                        volume_type="rootfs",
                        file_path="/media/sda1/oct-backup/soundtouch-ABC123-20250101-rootfs.tgz",
                        device_id="ABC123",
                        backup_date="20250101",
                    )
                ],
            ),
            BackupSet(
                device_id="ABC123",
                backup_date="20250512",
                files=[
                    BackupFileInfo(
                        filename="soundtouch-ABC123-20250512-rootfs.tgz",
                        volume_type="rootfs",
                        file_path="/media/sda1/oct-backup/soundtouch-ABC123-20250512-rootfs.tgz",
                        device_id="ABC123",
                        backup_date="20250512",
                    )
                ],
            ),
        ]
        selected = RestoreService._select_backup_set(sets, "ABC123")
        assert selected is not None
        assert selected.backup_date == "20250512"


class TestFindUsbBackups:
    """T012: Tests for _find_usb_backups() with mocked SSH."""

    @pytest.fixture
    def service(self):
        return RestoreService()

    @pytest.mark.asyncio
    async def test_usb_not_mounted(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output="", stderr="", exit_code=1)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_ssh
        mock_ctx.__aexit__.return_value = False

        with patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            return_value=mock_ctx,
        ):
            result = await service._find_usb_backups("192.168.1.50")
            assert result == []

    @pytest.mark.asyncio
    async def test_lists_tgz_files(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.side_effect = [
            MagicMock(output="/media/sda1", stderr="", exit_code=0),
            MagicMock(
                output="soundtouch-ABC123-20250512-rootfs.tgz\nsoundtouch-ABC123-20250512-nv.tgz\n",
                stderr="",
                exit_code=0,
            ),
        ]
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_ssh
        mock_ctx.__aexit__.return_value = False

        with patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            return_value=mock_ctx,
        ):
            files = await service._find_usb_backups("192.168.1.50")
            assert len(files) == 2
            assert files[0].volume_type == "rootfs"
            assert files[1].volume_type == "persistent"


class TestRestoreHosts:
    """T034: Tests for _restore_hosts()."""

    @pytest.fixture
    def service(self):
        return RestoreService()

    @pytest.mark.asyncio
    async def test_removes_oct_block(self, service):
        hosts_content = (
            "127.0.0.1 localhost\n"
            "# OCT-START\n"
            "192.168.1.100 bose.vtuner.com\n"
            "192.168.1.100 streaming.bose.com\n"
            "# OCT-END\n"
            "192.168.1.1 router\n"
        )
        mock_ssh = AsyncMock()
        mock_ssh.execute.side_effect = [
            # Read /etc/hosts
            MagicMock(output=hosts_content, exit_code=0),
            # Write back
            MagicMock(output="", exit_code=0),
        ]

        step = await service._restore_hosts(mock_ssh)
        assert step.status == StepStatus.COMPLETED
        # Verify the written content doesn't contain OCT block
        write_call = mock_ssh.execute.call_args_list[1]
        written_cmd = write_call[0][0]  # command string
        # Extract base64 from "echo '<b64>' | base64 -d > /etc/hosts"
        import base64 as b64mod

        b64_str = written_cmd.split("'")[1]
        decoded = b64mod.b64decode(b64_str).decode()
        assert "OCT-START" not in decoded
        assert "router" in decoded
        assert "localhost" in decoded

    @pytest.mark.asyncio
    async def test_skips_if_no_oct_block(self, service):
        hosts_content = "127.0.0.1 localhost\n192.168.1.1 router\n"
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output=hosts_content, exit_code=0)

        step = await service._restore_hosts(mock_ssh)
        assert step.status == StepStatus.SKIPPED


class TestRemoveRemoteServices:
    """T036: Tests for _remove_remote_services()."""

    @pytest.fixture
    def service(self):
        return RestoreService()

    @pytest.mark.asyncio
    async def test_removes_file(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=0)

        step = await service._remove_remote_services(mock_ssh)
        assert step.status == StepStatus.COMPLETED
        mock_ssh.execute.assert_called_once()
        cmd = mock_ssh.execute.call_args[0][0]
        assert "rm -f" in cmd
        assert "remote_services" in cmd

    @pytest.mark.asyncio
    async def test_idempotent_no_error(self, service):
        mock_ssh = AsyncMock()
        # rm -f never errors even if file doesn't exist
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=0)

        step = await service._remove_remote_services(mock_ssh)
        assert step.status == StepStatus.COMPLETED


class TestRestorePresets:
    """T032: Tests for _restore_presets()."""

    @pytest.fixture
    def service(self):
        return RestoreService()

    @pytest.mark.asyncio
    async def test_clean_mode_copies_template(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.side_effect = [
            # find Presets.xml
            MagicMock(
                output="/mnt/nv/BoseApp-Persistence/1/Presets.xml\n",
                exit_code=0,
            ),
            # write file (base64 pipe or scp)
            MagicMock(output="", exit_code=0),
        ]

        step = await service._restore_presets(mock_ssh, restore_type="clean")
        assert step.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_skips_if_no_presets_found(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=1)

        step = await service._restore_presets(mock_ssh, restore_type="clean")
        assert step.status == StepStatus.SKIPPED


class TestValidateArchive:
    """T014: Tests for _validate_archive()."""

    @pytest.fixture
    def service(self):
        return RestoreService()

    @pytest.mark.asyncio
    async def test_valid_rootfs_archive(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(
            output="opt/Bose/etc/SoundTouchSdkPrivateCfg.xml\nopt/Bose/bin/foo\n",
            exit_code=0,
        )
        info = BackupFileInfo(
            filename="soundtouch-ABC-20250512-rootfs.tgz",
            volume_type="rootfs",
            file_path="/media/sda1/oct-backup/soundtouch-ABC-20250512-rootfs.tgz",
        )
        await service._validate_archive(mock_ssh, info)
        assert info.validation_status == ValidationStatus.VALID

    @pytest.mark.asyncio
    async def test_valid_nv_archive(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(
            output="mnt/nv/Presets.xml\nmnt/nv/SoundTouchSdkPrivateCfg.xml\n",
            exit_code=0,
        )
        info = BackupFileInfo(
            filename="soundtouch-ABC-20250512-nv.tgz",
            volume_type="persistent",
            file_path="/media/sda1/oct-backup/soundtouch-ABC-20250512-nv.tgz",
        )
        await service._validate_archive(mock_ssh, info)
        assert info.validation_status == ValidationStatus.VALID

    @pytest.mark.asyncio
    async def test_corrupt_archive(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=2)
        info = BackupFileInfo(
            filename="soundtouch-ABC-20250512-rootfs.tgz",
            volume_type="rootfs",
            file_path="/media/sda1/oct-backup/soundtouch-ABC-20250512-rootfs.tgz",
        )
        await service._validate_archive(mock_ssh, info)
        assert info.validation_status == ValidationStatus.INVALID
        assert "corrupt" in info.validation_message

    @pytest.mark.asyncio
    async def test_empty_archive(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=0)
        info = BackupFileInfo(
            filename="soundtouch-ABC-20250512-rootfs.tgz",
            volume_type="rootfs",
            file_path="/media/sda1/oct-backup/soundtouch-ABC-20250512-rootfs.tgz",
        )
        await service._validate_archive(mock_ssh, info)
        assert info.validation_status == ValidationStatus.INVALID
        assert "empty" in info.validation_message

    @pytest.mark.asyncio
    async def test_wrong_paths_gives_warning(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(
            output="usr/local/bin/something\nvar/log/test.log\n",
            exit_code=0,
        )
        info = BackupFileInfo(
            filename="soundtouch-ABC-20250512-rootfs.tgz",
            volume_type="rootfs",
            file_path="/media/sda1/oct-backup/soundtouch-ABC-20250512-rootfs.tgz",
        )
        await service._validate_archive(mock_ssh, info)
        assert info.validation_status == ValidationStatus.WARNING
        assert "opt/Bose/" in info.validation_message


class TestPreRestoreSnapshot:
    """T028: Tests for _pre_restore_snapshot()."""

    @pytest.mark.asyncio
    async def test_snapshot_success(self):
        mock_wizard = AsyncMock()
        mock_wizard.backup_all.return_value = {"success": True}
        service = RestoreService(wizard_service=mock_wizard)

        step = await service._pre_restore_snapshot("192.168.1.100", "ABC123")
        assert step.status == StepStatus.COMPLETED
        assert step.name == RestoreStepName.PRE_SNAPSHOT

    @pytest.mark.asyncio
    async def test_snapshot_failure(self):
        mock_wizard = AsyncMock()
        mock_wizard.backup_all.return_value = {"success": False, "message": "USB full"}
        service = RestoreService(wizard_service=mock_wizard)

        step = await service._pre_restore_snapshot("192.168.1.100", "ABC123")
        assert step.status == StepStatus.FAILED
        assert "USB full" in step.message

    @pytest.mark.asyncio
    async def test_snapshot_exception(self):
        mock_wizard = AsyncMock()
        mock_wizard.backup_all.side_effect = RuntimeError("SSH failed")
        service = RestoreService(wizard_service=mock_wizard)

        step = await service._pre_restore_snapshot("192.168.1.100", "ABC123")
        assert step.status == StepStatus.FAILED
        assert "SSH failed" in step.error

    @pytest.mark.asyncio
    async def test_snapshot_skipped_without_wizard(self):
        service = RestoreService(wizard_service=None)

        step = await service._pre_restore_snapshot("192.168.1.100", "ABC123")
        assert step.status == StepStatus.SKIPPED


class TestRebootDevice:
    """T038: Tests for _reboot_device()."""

    @pytest.fixture
    def service(self):
        return RestoreService()

    @pytest.mark.asyncio
    async def test_reboot_success(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=0)

        step = await service._reboot_device(mock_ssh)
        assert step.status == StepStatus.COMPLETED
        assert step.name == RestoreStepName.REBOOT
        mock_ssh.execute.assert_called_once_with("reboot")

    @pytest.mark.asyncio
    async def test_reboot_ssh_disconnect_expected(self, service):
        """SSH disconnect on reboot is normal — should still complete."""
        mock_ssh = AsyncMock()
        mock_ssh.execute.side_effect = ConnectionResetError("Connection lost")

        step = await service._reboot_device(mock_ssh)
        assert step.status == StepStatus.COMPLETED
        assert "Reboot command sent" in step.message


class TestExecuteRestoreOrchestration:
    """T040: Tests for execute_restore() full orchestration."""

    @pytest.mark.asyncio
    async def test_clean_restore_all_steps_pass(self):
        mock_wizard = AsyncMock()
        mock_wizard.backup_all.return_value = {"success": True}
        mock_repo = AsyncMock()
        service = RestoreService(wizard_service=mock_wizard, device_repo=mock_repo)

        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=0)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_ssh
        mock_ctx.__aexit__.return_value = False

        with patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            return_value=mock_ctx,
        ):
            result = await service.execute_restore("192.168.1.100", "ABC123", "clean")

        assert result.success is True
        assert result.restore_type == "clean"
        assert len(result.steps) >= 4
        mock_repo.update_setup_status.assert_called_once_with("ABC123", "restored")

    @pytest.mark.asyncio
    async def test_restore_with_skip_snapshot(self):
        service = RestoreService()

        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=0)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_ssh
        mock_ctx.__aexit__.return_value = False

        with patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            return_value=mock_ctx,
        ):
            result = await service.execute_restore(
                "192.168.1.100", "ABC123", "clean", skip_snapshot=True
            )

        # No pre-snapshot step when skipped
        step_names = [s.name for s in result.steps]
        assert RestoreStepName.PRE_SNAPSHOT not in step_names

    @pytest.mark.asyncio
    async def test_step_failure_tracked(self):
        service = RestoreService()

        mock_ssh = AsyncMock()
        # cat /etc/hosts fails → _restore_hosts will fail
        mock_ssh.execute.side_effect = [
            MagicMock(output="", exit_code=0),  # remount rw /
            MagicMock(output="", exit_code=0),  # remount rw /mnt/nv
            MagicMock(output="", exit_code=0),  # rm -f overrides (config step1)
            MagicMock(output="", exit_code=0),  # rm -f overrides (config step2)
            MagicMock(output="", exit_code=1),  # find Presets.xml → not found
            MagicMock(output="", exit_code=1),  # cat /etc/hosts → fail
            MagicMock(output="", exit_code=0),  # rm -f remote_services
            MagicMock(output="", exit_code=0),  # remount ro /mnt/nv
            MagicMock(output="", exit_code=0),  # remount ro /
        ]
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_ssh
        mock_ctx.__aexit__.return_value = False

        with patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            return_value=mock_ctx,
        ):
            result = await service.execute_restore(
                "192.168.1.100", "ABC123", "clean", skip_snapshot=True
            )

        # At least some steps should exist
        assert len(result.steps) >= 3
        # Hosts step should be failed
        hosts_step = next(
            (s for s in result.steps if s.name == RestoreStepName.HOSTS), None
        )
        assert hosts_step is not None
        assert hosts_step.status == StepStatus.FAILED


class TestScanBackupsOrchestration:
    """Additional coverage tests for scan_backups() orchestration."""

    @pytest.mark.asyncio
    async def test_scan_usb_not_mounted(self):
        service = RestoreService()

        mock_ssh = AsyncMock()
        # _find_usb_backups: USB not mounted
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=1)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_ssh
        mock_ctx.__aexit__.return_value = False

        with patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            return_value=mock_ctx,
        ):
            result = await service.scan_backups("192.168.1.100", "ABC123")

        assert result.usb_mounted is False
        assert "not detected" in result.error

    @pytest.mark.asyncio
    async def test_scan_usb_mounted_but_empty(self):
        service = RestoreService()

        call_count = [0]

        def create_ctx(*args, **kwargs):
            mock_ssh = AsyncMock()
            if call_count[0] == 0:
                # _find_usb_backups: USB mounted, no files
                mock_ssh.execute.side_effect = [
                    MagicMock(output="/media/sda1", exit_code=0),
                    MagicMock(output="", exit_code=1),
                ]
            else:
                # check-usb: USB is mounted
                mock_ssh.execute.return_value = MagicMock(
                    output="/media/sda1", exit_code=0
                )
            call_count[0] += 1
            ctx = AsyncMock()
            ctx.__aenter__.return_value = mock_ssh
            ctx.__aexit__.return_value = False
            return ctx

        with patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            side_effect=create_ctx,
        ):
            result = await service.scan_backups("192.168.1.100", "ABC123")

        assert result.usb_mounted is True
        assert "No backup files" in result.error

    @pytest.mark.asyncio
    async def test_scan_with_validation_and_selection(self):
        service = RestoreService()

        call_count = [0]

        def create_ctx(*args, **kwargs):
            mock_ssh = AsyncMock()
            if call_count[0] == 0:
                # _find_usb_backups: files found
                mock_ssh.execute.side_effect = [
                    MagicMock(output="/media/sda1", exit_code=0),
                    MagicMock(
                        output="soundtouch-ABC123-20260101-rootfs.tgz\nsoundtouch-ABC123-20260101-nv.tgz\n",
                        exit_code=0,
                    ),
                ]
            else:
                # validate-archives: valid archives
                mock_ssh.execute.return_value = MagicMock(
                    output="opt/Bose/etc/config.xml\n", exit_code=0
                )
            call_count[0] += 1
            ctx = AsyncMock()
            ctx.__aenter__.return_value = mock_ssh
            ctx.__aexit__.return_value = False
            return ctx

        with patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            side_effect=create_ctx,
        ):
            result = await service.scan_backups("192.168.1.100", "ABC123")

        assert result.usb_mounted is True
        assert result.selected_set is not None
        assert result.selected_set.device_id == "ABC123"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_scan_no_matching_device(self):
        service = RestoreService()

        call_count = [0]

        def create_ctx(*args, **kwargs):
            mock_ssh = AsyncMock()
            if call_count[0] == 0:
                mock_ssh.execute.side_effect = [
                    MagicMock(output="/media/sda1", exit_code=0),
                    MagicMock(
                        output="soundtouch-OTHER-20260101-rootfs.tgz\n",
                        exit_code=0,
                    ),
                ]
            else:
                mock_ssh.execute.return_value = MagicMock(
                    output="opt/Bose/etc/config.xml\n", exit_code=0
                )
            call_count[0] += 1
            ctx = AsyncMock()
            ctx.__aenter__.return_value = mock_ssh
            ctx.__aexit__.return_value = False
            return ctx

        with patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            side_effect=create_ctx,
        ):
            result = await service.scan_backups("192.168.1.100", "ABC123")

        assert result.selected_set is None
        assert "No matching backup" in result.error


class TestRestoreConfigBackupMode:
    """Coverage tests for _restore_config() in backup mode."""

    @pytest.fixture
    def service(self):
        return RestoreService()

    @pytest.mark.asyncio
    async def test_backup_mode_extracts_and_cleans(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.return_value = MagicMock(output="", exit_code=0)

        backup_set = {
            "files": [
                {
                    "file_path": "/media/sda1/oct-backup/rootfs.tgz",
                    "volume_type": "rootfs",
                },
                {
                    "file_path": "/media/sda1/oct-backup/nv.tgz",
                    "volume_type": "persistent",
                },
            ]
        }

        step = await service._restore_config(mock_ssh, "backup", backup_set)
        assert step.status == StepStatus.COMPLETED
        # Should have called tar for rootfs and persistent
        assert mock_ssh.execute.call_count >= 3

    @pytest.mark.asyncio
    async def test_backup_mode_deletes_override_on_extract_fail(self, service):
        mock_ssh = AsyncMock()
        # First call (rootfs tar) succeeds, then persistent tar fails, then rm succeeds
        mock_ssh.execute.side_effect = [
            MagicMock(output="", exit_code=0),  # rootfs tar
            MagicMock(output="", exit_code=1),  # nv tar extract fail (override 1)
            MagicMock(output="", exit_code=0),  # rm -f override 1
            MagicMock(output="", exit_code=1),  # nv tar extract fail (override 2)
            MagicMock(output="", exit_code=0),  # rm -f override 2
        ]

        backup_set = {
            "files": [
                {"file_path": "/media/sda1/rootfs.tgz", "volume_type": "rootfs"},
                {"file_path": "/media/sda1/nv.tgz", "volume_type": "persistent"},
            ]
        }

        step = await service._restore_config(mock_ssh, "backup", backup_set)
        assert step.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_config_exception_captured(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.side_effect = RuntimeError("SSH crashed")

        step = await service._restore_config(mock_ssh, "clean")
        assert step.status == StepStatus.FAILED
        assert "SSH crashed" in step.error


class TestRestorePresetsBackupMode:
    """Coverage tests for _restore_presets() in backup mode."""

    @pytest.fixture
    def service(self):
        return RestoreService()

    @pytest.mark.asyncio
    async def test_backup_mode_extract_success(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.side_effect = [
            # find Presets.xml
            MagicMock(output="/mnt/nv/BoseApp/Presets.xml\n", exit_code=0),
            # tar extract from nv archive succeeds
            MagicMock(output="", exit_code=0),
        ]

        backup_set = {
            "files": [
                {"file_path": "/media/sda1/nv.tgz", "volume_type": "persistent"},
            ]
        }

        step = await service._restore_presets(mock_ssh, "backup", backup_set)
        assert step.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_backup_mode_fallback_to_clean(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.side_effect = [
            # find Presets.xml
            MagicMock(output="/mnt/nv/BoseApp/Presets.xml\n", exit_code=0),
            # tar extract fails (no Presets.xml in archive)
            MagicMock(output="", exit_code=1),
            # write empty template (fallback)
            MagicMock(output="", exit_code=0),
        ]

        backup_set = {
            "files": [
                {"file_path": "/media/sda1/nv.tgz", "volume_type": "persistent"},
            ]
        }

        step = await service._restore_presets(mock_ssh, "backup", backup_set)
        assert step.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_presets_exception_captured(self, service):
        mock_ssh = AsyncMock()
        mock_ssh.execute.side_effect = RuntimeError("Connection lost")

        step = await service._restore_presets(mock_ssh, "clean")
        assert step.status == StepStatus.FAILED
        assert "Connection lost" in step.error
