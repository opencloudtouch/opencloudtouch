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
    def test_valid_full_url(self):
        """Test with full URL including protocol and port."""
        req = ConfigModifyRequest(
            device_ip=VALID_IPV4, target_addr="http://192.168.1.100:7777"
        )
        assert req.device_ip == VALID_IPV4
        assert req.target_addr == "http://192.168.1.100:7777"

    def test_hostname_without_protocol(self):
        """Test hostname without protocol - should add http."""
        req = ConfigModifyRequest(device_ip=VALID_IPV4, target_addr="oct.local")
        assert req.target_addr == "http://oct.local:7777"

    def test_ip_without_port(self):
        """Test IP without port - should add default 7777."""
        req = ConfigModifyRequest(device_ip=VALID_IPV4, target_addr="10.0.0.1")
        assert req.target_addr == "http://10.0.0.1:7777"

    def test_hostname_with_port_no_protocol(self):
        """Test hostname with port but no protocol."""
        req = ConfigModifyRequest(device_ip=VALID_IPV4, target_addr="myserver:8080")
        assert req.target_addr == "http://myserver:8080"

    def test_https_url(self):
        """Test HTTPS URL."""
        req = ConfigModifyRequest(
            device_ip=VALID_IPV4, target_addr="https://oct.local:443"
        )
        assert req.target_addr == "https://oct.local:443"

    def test_invalid_device_ip_raises(self):
        with pytest.raises(ValidationError):
            ConfigModifyRequest(device_ip="bad-ip", target_addr="http://oct.local")

    def test_invalid_target_addr_raises(self):
        """Test invalid target address format."""
        with pytest.raises(ValidationError):
            ConfigModifyRequest(device_ip=VALID_IPV4, target_addr="not a valid url")

    def test_empty_target_addr_raises(self):
        """Test empty target address."""
        with pytest.raises(ValidationError):
            ConfigModifyRequest(device_ip=VALID_IPV4, target_addr="")


class TestHostsModifyRequestValidation:
    def test_valid_full_url(self):
        """Test with full URL."""
        req = HostsModifyRequest(
            device_ip=VALID_IPV4, target_addr="http://10.0.0.1:7777"
        )
        assert req.device_ip == VALID_IPV4
        assert req.target_addr == "http://10.0.0.1:7777"

    def test_hostname_normalized(self):
        """Test hostname gets normalized with defaults."""
        req = HostsModifyRequest(device_ip=VALID_IPV4, target_addr="oct.local")
        assert req.target_addr == "http://oct.local:7777"

    def test_invalid_device_ip_raises(self):
        with pytest.raises(ValidationError):
            HostsModifyRequest(device_ip="garbage", target_addr="http://oct.local")

    def test_invalid_target_addr_raises(self):
        """Test invalid target address."""
        with pytest.raises(ValidationError):
            HostsModifyRequest(device_ip=VALID_IPV4, target_addr="@invalid!")

    def test_default_include_optional(self):
        req = HostsModifyRequest(device_ip=VALID_IPV4, target_addr="oct.local")
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
