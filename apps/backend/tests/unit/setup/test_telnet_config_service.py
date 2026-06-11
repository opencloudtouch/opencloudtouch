"""Tests for TelnetConfigService (Issue #352 — Wave SoundTouch IV).

Covers:
- configure_urls() with mocked telnet client
- verify_configuration() with sample XML response
- reboot() sends correct command
- Input validation (invalid IPs rejected)
- Error cases: connection timeout, command failure
- check_device_connectivity returns telnet_available + setup_method
"""

from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.setup.ssh_client import CommandResult, SSHConnectionResult
from opencloudtouch.setup.telnet_config_service import TelnetConfigService

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_telnet_client():
    """Create a mocked SoundTouchTelnetClient."""
    client = AsyncMock()
    client.connect = AsyncMock(
        return_value=SSHConnectionResult(success=True, output="SoundTouch>")
    )
    client.execute = AsyncMock(
        return_value=CommandResult(success=True, output="OK", exit_code=0)
    )
    client.close = AsyncMock()
    return client


# ── TelnetConfigService.__init__ Validation ───────────────────────────────────


class TestTelnetConfigServiceValidation:
    """Input validation tests."""

    def test_valid_ipv4(self):
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")
        assert service.device_ip == "192.168.1.100"
        assert service.oct_host == "192.168.1.50"

    def test_valid_ipv6(self):
        service = TelnetConfigService("::1", "192.168.1.50")
        assert service.device_ip == "::1"

    def test_invalid_device_ip_rejected(self):
        with pytest.raises(ValueError, match="Invalid IP"):
            TelnetConfigService("not-an-ip", "192.168.1.50")

    def test_empty_oct_host_is_none(self):
        """Empty oct_host → oct_host is None (optional for verify/reboot)."""
        service = TelnetConfigService("192.168.1.100", "")
        assert service.oct_host is None

    def test_whitespace_only_oct_host_is_none(self):
        """Whitespace-only oct_host → oct_host is None."""
        service = TelnetConfigService("192.168.1.100", "   ")
        assert service.oct_host is None

    def test_default_port(self):
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")
        assert service.port == 7777

    def test_custom_port(self):
        service = TelnetConfigService("192.168.1.100", "192.168.1.50", port=8080)
        assert service.port == 8080


# ── configure_urls() ──────────────────────────────────────────────────────────


class TestConfigureUrls:
    """Tests for configure_urls()."""

    @pytest.mark.asyncio
    async def test_configure_urls_success(self, mock_telnet_client):
        """All 4 URLs configured + envswitch applied → success."""
        service = TelnetConfigService("192.168.1.100", "192.168.1.50", port=7777)

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.configure_urls()

        assert result.success is True
        assert len(result.urls_configured) == 4
        assert result.envswitch_applied is True
        assert result.errors == []

        # Verify URLs are correct
        base = "http://192.168.1.50:7777"
        assert (
            result.urls_configured["bmxRegistryUrl"]
            == f"{base}/bmx/registry/v1/services"
        )
        assert result.urls_configured["margeServerUrl"] == base
        assert result.urls_configured["statsServerUrl"] == base
        assert result.urls_configured["swUpdateUrl"] == f"{base}/updates/soundtouch"

        # 4 sys configuration commands + 1 envswitch = 5 execute calls
        assert mock_telnet_client.execute.call_count == 5

    @pytest.mark.asyncio
    async def test_configure_urls_connection_failure(self, mock_telnet_client):
        """Connection failure → success=False with error."""
        mock_telnet_client.connect = AsyncMock(
            return_value=SSHConnectionResult(success=False, error="Connection refused")
        )
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.configure_urls()

        assert result.success is False
        assert "Connection failed" in result.errors[0]
        assert result.urls_configured == {}

    @pytest.mark.asyncio
    async def test_configure_urls_command_failure(self, mock_telnet_client):
        """One URL command fails → partial success, errors reported."""
        call_count = 0

        async def mock_execute(cmd, timeout=5.0):
            nonlocal call_count
            call_count += 1
            # Fail on the second command (margeServerUrl)
            if call_count == 2:
                return CommandResult(
                    success=False, output="Error", exit_code=1, error="Command failed"
                )
            return CommandResult(success=True, output="OK", exit_code=0)

        mock_telnet_client.execute = mock_execute
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.configure_urls()

        assert result.success is False  # Not all 4 URLs configured
        assert len(result.urls_configured) == 3  # 3 of 4 succeeded
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_configure_urls_envswitch_failure(self, mock_telnet_client):
        """All URLs succeed but envswitch fails → success=False."""
        call_count = 0

        async def mock_execute(cmd, timeout=5.0):
            nonlocal call_count
            call_count += 1
            # Fail on the 5th call (envswitch)
            if call_count == 5:
                return CommandResult(
                    success=False, output="Error", exit_code=1, error="envswitch failed"
                )
            return CommandResult(success=True, output="OK", exit_code=0)

        mock_telnet_client.execute = mock_execute
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.configure_urls()

        assert result.success is False
        assert result.envswitch_applied is False
        assert len(result.urls_configured) == 4  # URLs were set
        assert any("envswitch" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_configure_urls_custom_port(self, mock_telnet_client):
        """Custom port appears in configured URLs."""
        service = TelnetConfigService("192.168.1.100", "10.0.0.1", port=8090)

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.configure_urls()

        assert result.success is True
        assert "http://10.0.0.1:8090" in result.urls_configured["margeServerUrl"]


# ── verify_configuration() ────────────────────────────────────────────────────


class TestVerifyConfiguration:
    """Tests for verify_configuration()."""

    SAMPLE_XML = """
    <CurrentSystemConfiguration>
        <bmxRegistryUrl>http://192.168.1.50:7777/bmx/registry/v1/services</bmxRegistryUrl>
        <margeServerUrl>http://192.168.1.50:7777</margeServerUrl>
        <statsServerUrl>http://192.168.1.50:7777</statsServerUrl>
        <swUpdateUrl>http://192.168.1.50:7777/updates/soundtouch</swUpdateUrl>
    </CurrentSystemConfiguration>
    """

    @pytest.mark.asyncio
    async def test_verify_success(self, mock_telnet_client):
        """Parses XML response and returns all 4 URL values."""
        mock_telnet_client.execute = AsyncMock(
            return_value=CommandResult(
                success=True, output=self.SAMPLE_XML, exit_code=0
            )
        )
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.verify_configuration()

        assert result.success is True
        assert len(result.configuration) == 4
        assert (
            result.configuration["bmxRegistryUrl"]
            == "http://192.168.1.50:7777/bmx/registry/v1/services"
        )
        assert result.configuration["margeServerUrl"] == "http://192.168.1.50:7777"
        assert result.configuration["statsServerUrl"] == "http://192.168.1.50:7777"
        assert (
            result.configuration["swUpdateUrl"]
            == "http://192.168.1.50:7777/updates/soundtouch"
        )

    @pytest.mark.asyncio
    async def test_verify_connection_failure(self, mock_telnet_client):
        """Connection failure → success=False."""
        mock_telnet_client.connect = AsyncMock(
            return_value=SSHConnectionResult(success=False, error="Timeout")
        )
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.verify_configuration()

        assert result.success is False
        assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_verify_command_failure(self, mock_telnet_client):
        """getpdo command fails → success=False."""
        mock_telnet_client.execute = AsyncMock(
            return_value=CommandResult(
                success=False, output="", exit_code=1, error="Command not found"
            )
        )
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.verify_configuration()

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_verify_partial_xml(self, mock_telnet_client):
        """Partial XML (missing tags) → returns only found keys."""
        partial_xml = """
        <CurrentSystemConfiguration>
            <bmxRegistryUrl>http://1.2.3.4:7777/bmx/registry/v1/services</bmxRegistryUrl>
        </CurrentSystemConfiguration>
        """
        mock_telnet_client.execute = AsyncMock(
            return_value=CommandResult(success=True, output=partial_xml, exit_code=0)
        )
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.verify_configuration()

        assert result.success is True
        assert len(result.configuration) == 1
        assert "bmxRegistryUrl" in result.configuration


# ── reboot() ──────────────────────────────────────────────────────────────────


class TestReboot:
    """Tests for reboot()."""

    @pytest.mark.asyncio
    async def test_reboot_success(self, mock_telnet_client):
        """Successful reboot returns True."""
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.reboot()

        assert result is True
        # Verify "sys reboot" was sent
        mock_telnet_client.execute.assert_called_once_with("sys reboot", timeout=5.0)

    @pytest.mark.asyncio
    async def test_reboot_connection_failure(self, mock_telnet_client):
        """Connection failure returns False."""
        mock_telnet_client.connect = AsyncMock(
            return_value=SSHConnectionResult(success=False, error="Refused")
        )
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.reboot()

        assert result is False

    @pytest.mark.asyncio
    async def test_reboot_command_failure(self, mock_telnet_client):
        """Command failure returns False."""
        mock_telnet_client.execute = AsyncMock(
            return_value=CommandResult(
                success=False, output="Error", exit_code=1, error="Failed"
            )
        )
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            result = await service.reboot()

        assert result is False


# ── check_device_connectivity with telnet ─────────────────────────────────────


class TestConnectivityWithTelnet:
    """Tests for check_device_connectivity returning telnet_available."""

    @pytest.fixture
    def setup_service(self):
        from opencloudtouch.setup.service import SetupService

        return SetupService()

    @pytest.mark.asyncio
    async def test_connectivity_ssh_and_telnet_available(self, setup_service):
        """Both SSH and Telnet available → setup_method=ssh."""
        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "opencloudtouch.setup.service.check_telnet_port",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await setup_service.check_device_connectivity("192.168.1.100")

        assert result["ssh_available"] is True
        assert result["telnet_available"] is True
        assert result["setup_method"] == "ssh"
        assert result["ready_for_setup"] is True

    @pytest.mark.asyncio
    async def test_connectivity_telnet_only(self, setup_service):
        """Only Telnet available → setup_method=telnet."""
        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "opencloudtouch.setup.service.check_telnet_port",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await setup_service.check_device_connectivity("192.168.1.100")

        assert result["ssh_available"] is False
        assert result["telnet_available"] is True
        assert result["setup_method"] == "telnet"
        assert result["ready_for_setup"] is True

    @pytest.mark.asyncio
    async def test_connectivity_nothing_available(self, setup_service):
        """Neither SSH nor Telnet → setup_method=none."""
        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "opencloudtouch.setup.service.check_telnet_port",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await setup_service.check_device_connectivity("192.168.1.100")

        assert result["ssh_available"] is False
        assert result["telnet_available"] is False
        assert result["setup_method"] == "none"
        assert result["ready_for_setup"] is False

    @pytest.mark.asyncio
    async def test_connectivity_ssh_only(self, setup_service):
        """Only SSH available → setup_method=ssh, telnet_available=False."""
        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "opencloudtouch.setup.service.check_telnet_port",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await setup_service.check_device_connectivity("192.168.1.100")

        assert result["ssh_available"] is True
        assert result["telnet_available"] is False
        assert result["setup_method"] == "ssh"
        assert result["ready_for_setup"] is True


# ── URL Building ──────────────────────────────────────────────────────────────


class TestUrlBuilding:
    """Tests for _build_urls() internal method."""

    def test_build_urls_default_port(self):
        service = TelnetConfigService("192.168.1.100", "192.168.1.50")
        urls = service._build_urls()

        assert (
            urls["bmxRegistryUrl"]
            == "http://192.168.1.50:7777/bmx/registry/v1/services"
        )
        assert urls["margeServerUrl"] == "http://192.168.1.50:7777"
        assert urls["statsServerUrl"] == "http://192.168.1.50:7777"
        assert urls["swUpdateUrl"] == "http://192.168.1.50:7777/updates/soundtouch"

    def test_build_urls_custom_port(self):
        service = TelnetConfigService("192.168.1.100", "myserver.local", port=8090)
        urls = service._build_urls()

        assert "http://myserver.local:8090" in urls["margeServerUrl"]
        assert "http://myserver.local:8090/bmx" in urls["bmxRegistryUrl"]

    def test_build_urls_hostname(self):
        """oct_host can be a hostname, not just IP."""
        service = TelnetConfigService("192.168.1.100", "hera")
        urls = service._build_urls()

        assert urls["margeServerUrl"] == "http://hera:7777"


# ── Command String Validation ─────────────────────────────────────────────────


class TestCommandStrings:
    """Verify exact command strings sent to Telnet (not just call count)."""

    @pytest.mark.asyncio
    async def test_exact_sys_configuration_commands(self, mock_telnet_client):
        """Each sys configuration command has correct key=value syntax."""
        service = TelnetConfigService("192.168.1.100", "10.0.0.5", port=7777)

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            await service.configure_urls()

        calls = [c.args[0] for c in mock_telnet_client.execute.call_args_list]
        base = "http://10.0.0.5:7777"

        assert (
            f"sys configuration bmxRegistryUrl {base}/bmx/registry/v1/services" in calls
        )
        assert f"sys configuration margeServerUrl {base}" in calls
        assert f"sys configuration statsServerUrl {base}" in calls
        assert f"sys configuration swUpdateUrl {base}/updates/soundtouch" in calls

    @pytest.mark.asyncio
    async def test_envswitch_correct_syntax(self, mock_telnet_client):
        """envswitch must use 'envswitch boseurls set <marge> <swupdate>' syntax."""
        service = TelnetConfigService("192.168.1.100", "10.0.0.5", port=7777)

        with patch(
            "opencloudtouch.setup.telnet_config_service.SoundTouchTelnetClient",
            return_value=mock_telnet_client,
        ):
            await service.configure_urls()

        calls = [c.args[0] for c in mock_telnet_client.execute.call_args_list]
        envswitch_calls = [c for c in calls if c.startswith("envswitch")]

        assert len(envswitch_calls) == 1
        expected = "envswitch boseurls set http://10.0.0.5:7777 http://10.0.0.5:7777/updates/soundtouch"
        assert envswitch_calls[0] == expected


# ── oct_host Validation (Command Injection Prevention) ────────────────────────


class TestOctHostValidation:
    """Defense-in-depth: TelnetConfigService rejects dangerous oct_host values."""

    def test_newline_in_oct_host_rejected(self):
        """Newline injection in oct_host must be rejected."""
        with pytest.raises(ValueError, match="Invalid oct_host"):
            TelnetConfigService("192.168.1.100", "evil\nhost")

    def test_carriage_return_in_oct_host_rejected(self):
        with pytest.raises(ValueError, match="Invalid oct_host"):
            TelnetConfigService("192.168.1.100", "evil\rhost")

    def test_semicolon_in_oct_host_rejected(self):
        with pytest.raises(ValueError, match="Invalid oct_host"):
            TelnetConfigService("192.168.1.100", "host;rm -rf /")

    def test_backtick_in_oct_host_rejected(self):
        with pytest.raises(ValueError, match="Invalid oct_host"):
            TelnetConfigService("192.168.1.100", "`whoami`")

    def test_space_in_oct_host_rejected(self):
        with pytest.raises(ValueError, match="Invalid oct_host"):
            TelnetConfigService("192.168.1.100", "host name")

    def test_valid_hostname_accepted(self):
        service = TelnetConfigService("192.168.1.100", "my-server.local")
        assert service.oct_host == "my-server.local"

    def test_valid_ip_accepted(self):
        service = TelnetConfigService("192.168.1.100", "10.0.0.1")
        assert service.oct_host == "10.0.0.1"

    def test_oct_host_none_allowed(self):
        """oct_host=None is valid (for verify/reboot only)."""
        service = TelnetConfigService("192.168.1.100")
        assert service.oct_host is None

    @pytest.mark.asyncio
    async def test_configure_urls_requires_oct_host(self):
        """configure_urls() raises ValueError when oct_host is None."""
        service = TelnetConfigService("192.168.1.100")
        with pytest.raises(ValueError, match="oct_host is required"):
            await service.configure_urls()


# ── API Model Validation (TelnetConfigureRequest) ─────────────────────────────


class TestTelnetConfigureRequestValidation:
    """Pydantic field_validator tests for TelnetConfigureRequest."""

    def test_valid_request(self):
        from opencloudtouch.setup.api_models import TelnetConfigureRequest

        req = TelnetConfigureRequest(
            device_ip="192.168.1.100", oct_host="10.0.0.5", port=7777
        )
        assert req.device_ip == "192.168.1.100"
        assert req.oct_host == "10.0.0.5"

    def test_newline_in_oct_host_rejected(self):
        from opencloudtouch.setup.api_models import TelnetConfigureRequest

        with pytest.raises(Exception):  # Pydantic ValidationError
            TelnetConfigureRequest(device_ip="192.168.1.100", oct_host="evil\nhost")

    def test_invalid_device_ip_rejected(self):
        from opencloudtouch.setup.api_models import TelnetConfigureRequest

        with pytest.raises(Exception):  # Pydantic ValidationError
            TelnetConfigureRequest(device_ip="not-an-ip", oct_host="10.0.0.5")

    def test_shell_metachar_in_oct_host_rejected(self):
        from opencloudtouch.setup.api_models import TelnetConfigureRequest

        with pytest.raises(Exception):  # Pydantic ValidationError
            TelnetConfigureRequest(device_ip="192.168.1.100", oct_host="host;rm -rf /")

    def test_valid_hostname_in_oct_host(self):
        from opencloudtouch.setup.api_models import TelnetConfigureRequest

        req = TelnetConfigureRequest(
            device_ip="192.168.1.100", oct_host="my-server.local"
        )
        assert req.oct_host == "my-server.local"
