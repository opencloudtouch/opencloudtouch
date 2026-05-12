"""
SoundTouch SSHitel Client

Async client for SSH and Telnet connections to SoundTouch devices.
Used for device configuration after USB-stick activation.

Supports legacy SSH algorithms required by SoundTouch devices:
- Host Key Algorithms: ssh-rsa, ssh-dss
- Key Exchange: diffie-hellman-group1-sha1, diffie-hellman-group14-sha1
- Ciphers: aes128-cbc, 3des-cbc

Tested with SoundTouch 10 (Firmware 0x0939).
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Legacy SSH algorithms required by SoundTouch firmware (shared across all SSH callers)
_SSH_HOST_KEY_ALGS = ["ssh-rsa", "rsa-sha2-512", "rsa-sha2-256", "ssh-dss"]
_SSH_KEX_ALGS = [
    "diffie-hellman-group1-sha1",
    "diffie-hellman-group14-sha1",
    "diffie-hellman-group-exchange-sha256",
    "ecdh-sha2-nistp256",
]
_SSH_ENCRYPTION_ALGS = ["aes128-cbc", "3des-cbc", "aes128-ctr", "aes256-ctr"]


@dataclass
class SSHConnectionResult:
    """Result of an SSH connection attempt."""

    success: bool
    output: str = ""
    error: Optional[str] = None


@dataclass
class CommandResult:
    """Result of executing a command over SSH."""

    success: bool
    output: str = ""
    exit_code: int = -1
    error: Optional[str] = None
    stderr: str = ""


class SoundTouchSSHClient:
    """
    Async SSH client for SoundTouch device configuration.

    Uses asyncssh for SSH connections. Falls back to telnet if needed.
    """

    def __init__(self, host: str, port: int = 22):
        self.host = host
        self.port = port
        self._connection = None

    async def connect(self, timeout: float = 10.0) -> SSHConnectionResult:
        """
        Establish SSH connection to device.

        SoundTouch devices use root user with no password when
        remote_services is enabled via USB stick.

        Enables legacy SSH algorithms required by older SoundTouch firmware:
        - HostKeyAlgorithms: ssh-rsa, ssh-dss
        - KexAlgorithms: diffie-hellman-group1-sha1, diffie-hellman-group14-sha1
        - Ciphers: aes128-cbc, 3des-cbc
        """
        try:
            # Try to import asyncssh (optional dependency)
            try:
                import asyncssh
            except ImportError:
                return SSHConnectionResult(
                    success=False,
                    error="asyncssh not installed. Run: pip install asyncssh",
                )

            logger.info("Connecting to %s:%s via SSH...", self.host, self.port)
            logger.debug(
                "SSH params: user=root, timeout=%.1fs, "
                "host_key_algs=[ssh-rsa,rsa-sha2-512,rsa-sha2-256,ssh-dss], "
                "kex=[dh-group1-sha1,dh-group14-sha1,dh-gex-sha256,ecdh-nistp256], "
                "ciphers=[aes128-cbc,3des-cbc,aes128-ctr,aes256-ctr]",
                timeout,
            )

            # Connect with no password (SoundTouch root has no password)
            # Enable legacy algorithms for old SoundTouch firmware
            # Type: ignore needed because asyncssh returns _ACMWrapper which mypy can't resolve
            self._connection = await asyncio.wait_for(  # type: ignore[func-returns-value]
                asyncssh.connect(  # type: ignore[arg-type]
                    self.host,
                    port=self.port,
                    username="root",
                    password="",
                    known_hosts=None,  # Skip host key verification for embedded devices
                    server_host_key_algs=_SSH_HOST_KEY_ALGS,
                    kex_algs=_SSH_KEX_ALGS,
                    encryption_algs=_SSH_ENCRYPTION_ALGS,
                ),
                timeout=timeout,
            )

            logger.info("SSH connection established to %s", self.host)
            return SSHConnectionResult(success=True, output="Connected")

        except asyncio.TimeoutError:
            error = (
                f"SSH connection timeout after {timeout}s to {self.host}:{self.port}"
            )
            logger.error(error)
            return SSHConnectionResult(success=False, error=error)
        except Exception as e:
            error = f"SSH connection failed to {self.host}:{self.port}: {type(e).__name__}: {e}"
            logger.error(error)
            return SSHConnectionResult(success=False, error=error)

    async def execute(self, command: str, timeout: float = 30.0) -> CommandResult:
        """Execute a command over SSH."""
        if not self._connection:
            return CommandResult(
                success=False, error="Not connected. Call connect() first."
            )

        try:
            logger.debug("SSH exec [%s]: %s", self.host, command)

            result = await asyncio.wait_for(
                self._connection.run(command), timeout=timeout
            )

            output = result.stdout or ""
            stderr = result.stderr or ""

            if stderr:
                output += f"\n[stderr]: {stderr}"

            exit_code = result.exit_status or 0
            logger.debug(
                "SSH result [%s]: exit=%d, stdout=%d bytes, stderr=%d bytes, out=%.200s",
                self.host,
                exit_code,
                len(result.stdout or ""),
                len(stderr),
                output[:200],
            )

            return CommandResult(
                success=exit_code == 0,
                output=output,
                exit_code=exit_code,
            )

        except asyncio.TimeoutError:
            logger.error(
                "SSH command timeout after %.0fs on %s: %s",
                timeout,
                self.host,
                command[:100],
            )
            return CommandResult(
                success=False, error=f"Command timeout after {timeout}s"
            )
        except Exception as e:
            logger.error(
                "SSH command failed on %s: %s: %s", self.host, type(e).__name__, e
            )
            return CommandResult(
                success=False, error=f"Command execution failed: {str(e)}"
            )

    async def close(self):
        """Close SSH connection."""
        if self._connection:
            self._connection.close()
            await self._connection.wait_closed()
            self._connection = None
            logger.info("SSH connection to %s closed", self.host)

    async def __aenter__(self):
        result = await self.connect()
        if not result.success:
            raise ConnectionError(
                f"SSH connection to {self.host} failed: {result.error}"
            )
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        await self.close()


class SoundTouchTelnetClient:
    """
    Async Telnet client for SoundTouch Port 17000.

    Used for basic commands when SSH is not available.
    """

    def __init__(self, host: str, port: int = 17000):
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def connect(self, timeout: float = 10.0) -> SSHConnectionResult:
        """Establish telnet connection to device."""
        try:
            logger.info("Connecting to %s:%s via Telnet...", self.host, self.port)

            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=timeout
            )

            # Read initial prompt
            await asyncio.sleep(0.5)
            initial = await self._read_available()

            logger.info("Telnet connection established to %s", self.host)
            return SSHConnectionResult(success=True, output=initial)

        except asyncio.TimeoutError:
            error = f"Telnet connection timeout after {timeout}s"
            logger.error(error)
            return SSHConnectionResult(success=False, error=error)
        except Exception as e:
            error = f"Telnet connection failed: {str(e)}"
            logger.error(error)
            return SSHConnectionResult(success=False, error=error)

    async def _read_available(self, timeout: float = 1.0) -> str:
        """Read all available data with timeout."""
        if not self._reader:
            return ""

        try:
            data = await asyncio.wait_for(self._reader.read(4096), timeout=timeout)
            return data.decode("utf-8", errors="ignore")
        except asyncio.TimeoutError:
            return ""

    async def execute(self, command: str, timeout: float = 5.0) -> CommandResult:
        """Execute a command over telnet."""
        if not self._writer or not self._reader:
            return CommandResult(
                success=False, error="Not connected. Call connect() first."
            )

        try:
            logger.debug("Telnet executing: %s", command)

            # Send command
            self._writer.write(f"{command}\r\n".encode())
            await self._writer.drain()

            # Wait for response
            await asyncio.sleep(0.3)
            output = await self._read_available(timeout)

            # Check for error indicators
            is_error = "Command not found" in output or "Error" in output

            return CommandResult(
                success=not is_error,
                output=output,
                exit_code=1 if is_error else 0,
            )

        except Exception as e:
            return CommandResult(
                success=False, error=f"Command execution failed: {str(e)}"
            )

    async def close(self):
        """Close telnet connection."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None
            logger.info("Telnet connection to %s closed", self.host)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        await self.close()


async def check_ssh_port(host: str, timeout: float = 5.0) -> bool:
    """
    Check if SSH is actually accessible on the device.

    Performs a real SSH handshake with legacy algorithms required by
    SoundTouch devices. Returns True only if authentication-level
    access is reached (not just TCP reachability).
    """
    try:
        import asyncssh
    except ImportError:
        logger.warning("asyncssh not installed – falling back to TCP check")
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, 22), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False

    try:
        conn = await asyncio.wait_for(
            asyncssh.connect(
                host,
                port=22,
                username="root",
                password="",
                known_hosts=None,
                server_host_key_algs=_SSH_HOST_KEY_ALGS,
                kex_algs=_SSH_KEX_ALGS,
                encryption_algs=_SSH_ENCRYPTION_ALGS,
            ),
            timeout=timeout,
        )
        conn.close()
        return True
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError, asyncssh.Error):
        return False


async def check_telnet_port(host: str, timeout: float = 5.0) -> bool:
    """
    Quick check if Telnet port 17000 is open on device.

    Returns True if port 17000 is reachable.
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, 17000), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return False
