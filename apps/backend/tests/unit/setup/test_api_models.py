"""Tests for Setup Wizard API request model validation.

Covers REFACT-017: IP address validation on all wizard request models.
"""

import pytest
from pydantic import ValidationError

from opencloudtouch.setup.api_models import (
    BackupRequest,
    ConfigModifyRequest,
    HostsModifyRequest,
    ListBackupsRequest,
    PortCheckRequest,
    RestoreRequest,
    VerifyRedirectRequest,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

VALID_IPV4 = "192.168.1.100"
VALID_IPV6 = "::1"
INVALID_IPS = [
    "not-an-ip",
    "256.0.0.1",
    "192.168.1",
    "",
    "http://evil.com",
    "file:///etc/passwd",
    "169.254.169.254",  # Still allowed (it's a valid IP unless we block it explicitly)
]


# ---------------------------------------------------------------------------
# WizardDeviceRequest base – tested via concrete subclasses
# ---------------------------------------------------------------------------


class TestPortCheckRequestValidation:
    def test_valid_ipv4_passes(self):
        req = PortCheckRequest(device_ip=VALID_IPV4)
        assert req.device_ip == VALID_IPV4

    def test_valid_ipv6_passes(self):
        req = PortCheckRequest(device_ip=VALID_IPV6)
        assert req.device_ip == VALID_IPV6

    @pytest.mark.parametrize("bad_ip", ["not-an-ip", "256.0.0.1", "192.168.1", ""])
    def test_invalid_ip_raises_validation_error(self, bad_ip):
        with pytest.raises(ValidationError) as exc_info:
            PortCheckRequest(device_ip=bad_ip)
        assert "Invalid IP address" in str(exc_info.value) or "value_error" in str(
            exc_info.value
        )

    def test_ssrf_hostname_rejected(self):
        with pytest.raises(ValidationError):
            PortCheckRequest(device_ip="http://internal-host")

    def test_whitespace_stripped_and_normalized(self):
        req = PortCheckRequest(device_ip="  192.168.1.100  ")
        assert req.device_ip == "192.168.1.100"

    def test_default_timeout(self):
        req = PortCheckRequest(device_ip=VALID_IPV4)
        assert req.timeout == 10.0

    def test_custom_timeout(self):
        req = PortCheckRequest(device_ip=VALID_IPV4, timeout=30.0)
        assert req.timeout == 30.0


class TestBackupRequestValidation:
    def test_valid_ip_passes(self):
        req = BackupRequest(device_ip=VALID_IPV4)
        assert req.device_ip == VALID_IPV4

    def test_invalid_ip_raises(self):
        with pytest.raises(ValidationError):
            BackupRequest(device_ip="not-an-ip")


class TestConfigModifyRequestValidation:
    def test_valid_device_and_oct_ip(self):
        req = ConfigModifyRequest(device_ip=VALID_IPV4, oct_ip="10.0.0.1")
        assert req.device_ip == VALID_IPV4
        assert req.oct_ip == "10.0.0.1"

    def test_invalid_device_ip_raises(self):
        with pytest.raises(ValidationError):
            ConfigModifyRequest(device_ip="bad-ip", oct_ip=VALID_IPV4)

    def test_invalid_oct_ip_raises(self):
        with pytest.raises(ValidationError):
            ConfigModifyRequest(device_ip=VALID_IPV4, oct_ip="bad-ip")

    def test_both_invalid_raises(self):
        with pytest.raises(ValidationError):
            ConfigModifyRequest(device_ip="bad1", oct_ip="bad2")


class TestHostsModifyRequestValidation:
    def test_valid_ips(self):
        req = HostsModifyRequest(device_ip=VALID_IPV4, oct_ip="10.0.0.1")
        assert req.device_ip == VALID_IPV4
        assert req.oct_ip == "10.0.0.1"

    def test_invalid_device_ip_raises(self):
        with pytest.raises(ValidationError):
            HostsModifyRequest(device_ip="garbage", oct_ip=VALID_IPV4)

    def test_invalid_oct_ip_raises(self):
        with pytest.raises(ValidationError):
            HostsModifyRequest(device_ip=VALID_IPV4, oct_ip="garbage")

    def test_default_include_optional(self):
        req = HostsModifyRequest(device_ip=VALID_IPV4, oct_ip="10.0.0.1")
        assert req.include_optional is True


class TestRestoreRequestValidation:
    def test_valid_ip_and_path(self):
        req = RestoreRequest(device_ip=VALID_IPV4, backup_path="/mnt/backup")
        assert req.device_ip == VALID_IPV4
        assert req.backup_path == "/mnt/backup"

    def test_invalid_ip_raises(self):
        with pytest.raises(ValidationError):
            RestoreRequest(device_ip="not-an-ip", backup_path="/mnt/backup")


class TestVerifyRedirectRequestValidation:
    def test_valid_ip_and_domain(self):
        req = VerifyRedirectRequest(
            device_ip=VALID_IPV4, domain="bose.com", expected_ip="192.168.1.1"
        )
        assert req.device_ip == VALID_IPV4
        assert req.domain == "bose.com"

    def test_invalid_device_ip_raises(self):
        with pytest.raises(ValidationError):
            VerifyRedirectRequest(
                device_ip="not-an-ip", domain="bose.com", expected_ip="192.168.1.1"
            )

    def test_expected_ip_accepts_hostname(self):
        """expected_ip can be a hostname (seen by browser), so no IP validation."""
        req = VerifyRedirectRequest(
            device_ip=VALID_IPV4, domain="bose.com", expected_ip="my-server.local"
        )
        assert req.expected_ip == "my-server.local"


class TestListBackupsRequestValidation:
    def test_valid_ip_passes(self):
        req = ListBackupsRequest(device_ip=VALID_IPV4)
        assert req.device_ip == VALID_IPV4

    def test_invalid_ip_raises(self):
        with pytest.raises(ValidationError):
            ListBackupsRequest(device_ip="not-an-ip")
