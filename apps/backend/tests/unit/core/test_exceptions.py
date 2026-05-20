"""Tests for custom exception hierarchy and constructors."""

from opencloudtouch.core.exceptions import (
    BackupScanError,
    DeviceConnectionError,
    DeviceNotFoundError,
    DomainValidationError,
    OpenCloudTouchError,
    RestoreError,
    SSHConnectionError,
    SSHOperationError,
)


class TestExceptionHierarchy:
    """All domain exceptions must inherit from OpenCloudTouchError."""

    def test_device_not_found_is_oct_error(self):
        assert issubclass(DeviceNotFoundError, OpenCloudTouchError)

    def test_device_connection_error_is_oct_error(self):
        assert issubclass(DeviceConnectionError, OpenCloudTouchError)

    def test_ssh_connection_error_is_oct_error(self):
        assert issubclass(SSHConnectionError, OpenCloudTouchError)

    def test_ssh_operation_error_is_oct_error(self):
        assert issubclass(SSHOperationError, OpenCloudTouchError)

    def test_restore_error_is_oct_error(self):
        assert issubclass(RestoreError, OpenCloudTouchError)

    def test_backup_scan_error_is_oct_error(self):
        assert issubclass(BackupScanError, OpenCloudTouchError)


class TestSSHOperationError:
    """SSHOperationError stores operation name and builds message."""

    def test_message_without_detail(self):
        err = SSHOperationError("192.168.1.1", "remount")
        assert "remount" in str(err)
        assert err.device_ip == "192.168.1.1"
        assert err.operation == "remount"

    def test_message_with_detail(self):
        err = SSHOperationError("10.0.0.1", "cat", "file not found")
        assert "cat" in str(err)
        assert "file not found" in str(err)


class TestRestoreError:
    """RestoreError stores device_ip, step, and optional message."""

    def test_message_without_detail(self):
        err = RestoreError("192.168.1.1", "backup")
        assert "backup" in str(err)
        assert "192.168.1.1" in str(err)
        assert err.step == "backup"

    def test_message_with_detail(self):
        err = RestoreError("10.0.0.1", "reboot", "timeout after 60s")
        assert "reboot" in str(err)
        assert "timeout after 60s" in str(err)
        assert err.device_ip == "10.0.0.1"


class TestBackupScanError:
    """BackupScanError stores device_ip."""

    def test_default_message(self):
        err = BackupScanError("192.168.1.1")
        assert "Backup scan failed" in str(err)
        assert err.device_ip == "192.168.1.1"

    def test_custom_message(self):
        err = BackupScanError("10.0.0.1", "USB not mounted")
        assert "USB not mounted" in str(err)


class TestDomainValidationError:
    """DomainValidationError stores optional field name."""

    def test_with_field(self):
        err = DomainValidationError("invalid IP", field="oct_ip")
        assert err.field == "oct_ip"
        assert "invalid IP" in str(err)

    def test_without_field(self):
        err = DomainValidationError("bad input")
        assert err.field is None
