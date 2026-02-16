"""
SoundTouch SSH/Telnet Client

Async client for SSH and Telnet connections to SoundTouch devices.
Used for device configuration after USB-stick activation.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


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

            logger.info(f"Connecting to {self.host}:{self.port} via SSH...")

            # Connect with no password (SoundTouch root has no password)
            self._connection = await asyncio.wait_for(
                asyncssh.connect(
                    self.host,
                    port=self.port,
                    username="root",
                    password="",
                    known_hosts=None,  # Skip host key verification for embedded devices
                ),
                timeout=timeout,
            )

            logger.info(f"SSH connection established to {self.host}")
            return SSHConnectionResult(success=True, output="Connected")

        except asyncio.TimeoutError:
            error = f"SSH connection timeout after {timeout}s"
            logger.error(error)
            return SSHConnectionResult(success=False, error=error)
        except Exception as e:
            error = f"SSH connection failed: {str(e)}"
            logger.error(error)
            return SSHConnectionResult(success=False, error=error)

    async def execute(self, command: str, timeout: float = 30.0) -> CommandResult:
        """Execute a command over SSH."""
        if not self._connection:
            return CommandResult(
                success=False, error="Not connected. Call connect() first."
            )

        try:
            logger.debug(f"Executing: {command}")

            result = await asyncio.wait_for(
                self._connection.run(command), timeout=timeout
            )

            output = result.stdout or ""
            stderr = result.stderr or ""

            if stderr:
                output += f"\n[stderr]: {stderr}"

            logger.debug(f"Command output: {output[:200]}...")

            return CommandResult(
                success=result.exit_status == 0,
                output=output,
                exit_code=result.exit_status or 0,
            )

        except asyncio.TimeoutError:
            return CommandResult(
                success=False, error=f"Command timeout after {timeout}s"
            )
        except Exception as e:
            return CommandResult(
                success=False, error=f"Command execution failed: {str(e)}"
            )

    async def close(self):
        """Close SSH connection."""
        if self._connection:
            self._connection.close()
            await self._connection.wait_closed()
            self._connection = None
            logger.info(f"SSH connection to {self.host} closed")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
            logger.info(f"Connecting to {self.host}:{self.port} via Telnet...")

            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=timeout
            )

            # Read initial prompt
            await asyncio.sleep(0.5)
            initial = await self._read_available()

            logger.info(f"Telnet connection established to {self.host}")
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
            logger.debug(f"Telnet executing: {command}")

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
            logger.info(f"Telnet connection to {self.host} closed")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def check_ssh_port(host: str, timeout: float = 5.0) -> bool:
    """
    Quick check if SSH port is open on device.

    Returns True if port 22 is reachable.
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, 22), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
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
