"""
Telnet configuration service for Wave SoundTouch IV.

Configures devices via Telnet port 17000 using `sys configuration`
commands instead of XML file editing. No filesystem access required —
all configuration through the Telnet command protocol.

Supported commands:
- sys configuration <key> <value>  — set a URL configuration value
- envswitch boseurls               — apply URL changes
- getpdo CurrentSystemConfiguration — read current configuration
- sys reboot                        — reboot the device
"""

import ipaddress
import logging
import re
from dataclasses import dataclass, field

from opencloudtouch.core.config import DEFAULT_PORT
from opencloudtouch.setup.ssh_client import SoundTouchTelnetClient

logger = logging.getLogger(__name__)

# URL configuration keys (same as SSH config_service tags)
_BMX_KEY = "bmxRegistryUrl"
_MARGE_KEY = "margeServerUrl"
_STATS_KEY = "statsServerUrl"
_SWUPDATE_KEY = "swUpdateUrl"


def _validate_oct_ip(value: str) -> str:
    """Validate that a string is a valid IPv4 or IPv6 address.

    Raises ValueError for invalid input.
    """
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        raise ValueError(f"Invalid IP address: {value!r}")


@dataclass
class TelnetConfigResult:
    """Result of a single Telnet configuration command."""

    key: str
    value: str
    success: bool
    error: str | None = None


@dataclass
class TelnetConfigureResult:
    """Aggregate result of configure_urls()."""

    success: bool
    urls_configured: dict[str, str] = field(default_factory=dict)
    envswitch_applied: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class TelnetVerifyResult:
    """Result of verify_configuration()."""

    success: bool
    configuration: dict[str, str] = field(default_factory=dict)
    error: str | None = None


class TelnetConfigService:
    """Configure Wave SoundTouch IV via Telnet port 17000.

    Uses ``sys configuration`` commands instead of XML file editing.
    No filesystem access — all config through Telnet command protocol.

    ``oct_host`` is only required for :meth:`configure_urls`.
    :meth:`verify_configuration` and :meth:`reboot` work without it.
    """

    # Hostname: letters, digits, hyphens, dots — NO shell metacharacters
    _HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9.-]{0,253}[a-zA-Z0-9])?$")

    def __init__(
        self, device_ip: str, oct_host: str | None = None, port: int = DEFAULT_PORT
    ):
        self.device_ip = _validate_oct_ip(device_ip)
        self.oct_host = self._validate_oct_host(oct_host) if oct_host and oct_host.strip() else None
        self.port = port
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @classmethod
    def _validate_oct_host(cls, value: str) -> str:
        """Validate oct_host: must be a valid IP or hostname (defense-in-depth)."""
        value = value.strip()
        if not value:
            raise ValueError("oct_host cannot be empty")
        # Valid IP?
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            pass
        # Valid hostname?
        if not cls._HOSTNAME_RE.match(value):
            raise ValueError(
                f"Invalid oct_host: {value!r} — only letters, digits, hyphens, dots allowed"
            )
        return value

    def _build_urls(self) -> dict[str, str]:
        """Build the 4 URL configuration values."""
        base = f"http://{self.oct_host}:{self.port}"  # noqa: S324
        return {
            _BMX_KEY: f"{base}/bmx/registry/v1/services",
            _MARGE_KEY: base,
            _STATS_KEY: base,
            _SWUPDATE_KEY: f"{base}/updates/soundtouch",
        }

    async def configure_urls(self) -> TelnetConfigureResult:
        """Send all 4 URL configuration commands + envswitch.

        Connects via Telnet, sends each ``sys configuration <key> <value>``
        command, then applies with ``envswitch boseurls set <marge> <swupdate>``.

        Raises :class:`ValueError` if ``oct_host`` was not provided at init.
        """
        if not self.oct_host:
            raise ValueError("oct_host is required for configure_urls()")

        result = TelnetConfigureResult(success=False)
        urls = self._build_urls()

        client = SoundTouchTelnetClient(host=self.device_ip)
        try:
            conn = await client.connect(timeout=10.0)
            if not conn.success:
                result.errors.append(f"Connection failed: {conn.error}")
                return result

            # Send each URL configuration command
            for key, value in urls.items():
                cmd = f"sys configuration {key} {value}"
                self.logger.info("Sending: %s", cmd)
                cmd_result = await client.execute(cmd, timeout=5.0)

                if cmd_result.success:
                    result.urls_configured[key] = value
                else:
                    error = f"{key}: {cmd_result.error or cmd_result.output}"
                    result.errors.append(error)
                    self.logger.error("Command failed for %s: %s", key, error)

            # Apply URL changes with envswitch (requires marge + swupdate URLs)
            marge_url = urls[_MARGE_KEY]
            swupdate_url = urls[_SWUPDATE_KEY]
            envswitch_cmd = f"envswitch boseurls set {marge_url} {swupdate_url}"
            self.logger.info("Sending: %s", envswitch_cmd)
            envswitch = await client.execute(envswitch_cmd, timeout=5.0)
            result.envswitch_applied = envswitch.success
            if not envswitch.success:
                result.errors.append(
                    f"envswitch failed: {envswitch.error or envswitch.output}"
                )

            # Success if all 4 URLs configured and envswitch applied
            result.success = (
                len(result.urls_configured) == 4 and result.envswitch_applied
            )

        except Exception as e:
            result.errors.append(f"Unexpected error: {e}")
            self.logger.exception("configure_urls failed")
        finally:
            await client.close()

        return result

    async def verify_configuration(self) -> TelnetVerifyResult:
        """Read current config via ``getpdo CurrentSystemConfiguration``.

        Parses the XML response and extracts URL values for verification.
        """
        client = SoundTouchTelnetClient(host=self.device_ip)
        try:
            conn = await client.connect(timeout=10.0)
            if not conn.success:
                return TelnetVerifyResult(
                    success=False, error=f"Connection failed: {conn.error}"
                )

            cmd_result = await client.execute(
                "getpdo CurrentSystemConfiguration", timeout=10.0
            )
            if not cmd_result.success:
                return TelnetVerifyResult(
                    success=False,
                    error=f"Command failed: {cmd_result.error or cmd_result.output}",
                )

            # Parse XML-like response for URL tags
            configuration: dict[str, str] = {}
            for key in (_BMX_KEY, _MARGE_KEY, _STATS_KEY, _SWUPDATE_KEY):
                pattern = re.compile(
                    rf"<{re.escape(key)}>(.*?)</{re.escape(key)}>", re.DOTALL
                )
                match = pattern.search(cmd_result.output)
                if match:
                    configuration[key] = match.group(1).strip()

            return TelnetVerifyResult(success=True, configuration=configuration)

        except Exception as e:
            self.logger.exception("verify_configuration failed")
            return TelnetVerifyResult(success=False, error=str(e))
        finally:
            await client.close()

    async def reboot(self) -> bool:
        """Send ``sys reboot`` command to device."""
        client = SoundTouchTelnetClient(host=self.device_ip)
        try:
            conn = await client.connect(timeout=10.0)
            if not conn.success:
                self.logger.error("Cannot connect for reboot: %s", conn.error)
                return False

            self.logger.info("Sending: sys reboot")
            cmd_result = await client.execute("sys reboot", timeout=5.0)
            return cmd_result.success

        except Exception:
            self.logger.exception("reboot failed")
            return False
        finally:
            await client.close()
