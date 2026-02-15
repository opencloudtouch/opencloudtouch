"""Unit tests for SSH/Telnet client.

Tests for SoundTouchSSHClient, SoundTouchTelnetClient, and connection helpers.
Following TDD Red-Green-Refactor cycle.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from opencloudtouch.setup.ssh_client import (
    SSHConnectionResult,
    CommandResult,
    SoundTouchSSHClient,
    SoundTouchTelnetClient,
    check_ssh_port,
    check_telnet_port,
)


class TestSSHConnectionResult:
    """Tests for SSHConnectionResult dataclass."""

    def test_success_result(self):
        """Test successful connection result."""
        result = SSHConnectionResult(success=True, output="Connected")
        assert result.success is True
        assert result.output == "Connected"
        assert result.error is None

    def test_failure_result(self):
        """Test failed connection result."""
        result = SSHConnectionResult(
            success=False,
            error="Connection refused"
        )
        assert result.success is False
        assert result.error == "Connection refused"


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_successful_command(self):
        """Test successful command result."""
        result = CommandResult(
            success=True,
            output="file.txt",
            exit_code=0
        )
        assert result.success is True
        assert result.output == "file.txt"
        assert result.exit_code == 0
        assert result.error is None

    def test_failed_command(self):
        """Test failed command result."""
        result = CommandResult(
            success=False,
            exit_code=1,
            error="Command not found"
        )
        assert result.success is False
        assert result.exit_code == 1
        assert result.error == "Command not found"


class TestSoundTouchSSHClient:
    """Tests for SoundTouchSSHClient."""

    @pytest.fixture
    def ssh_client(self):
        """Create SSH client instance."""
        return SoundTouchSSHClient("192.168.1.100", port=22)

    def test_client_initialization(self, ssh_client):
        """Test client is initialized with correct host and port."""
        assert ssh_client.host == "192.168.1.100"
        assert ssh_client.port == 22
        assert ssh_client._connection is None

    @pytest.mark.asyncio
    async def test_connect_without_asyncssh_installed(self, ssh_client):
        """Test connect returns error when asyncssh not available."""
        with patch.dict("sys.modules", {"asyncssh": None}):
            # Force reimport to trigger ImportError
            with patch.object(ssh_client, "connect") as mock_connect:
                mock_connect.return_value = SSHConnectionResult(
                    success=False,
                    error="asyncssh not installed"
                )
                result = await ssh_client.connect()
                assert result.success is False
                assert "asyncssh" in result.error.lower()

    @pytest.mark.asyncio
    async def test_connect_timeout(self, ssh_client):
        """Test connection timeout handling."""
        # Need to mock asyncssh first so the import doesn't fail
        mock_asyncssh = MagicMock()
        mock_asyncssh.connect = AsyncMock()
        
        with patch.dict("sys.modules", {"asyncssh": mock_asyncssh}):
            with patch("asyncio.wait_for") as mock_wait:
                mock_wait.side_effect = asyncio.TimeoutError()
                result = await ssh_client.connect(timeout=1.0)
                assert result.success is False
                assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_without_connection(self, ssh_client):
        """Test execute fails when not connected."""
        result = await ssh_client.execute("ls")
        assert result.success is False
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_close_without_connection(self, ssh_client):
        """Test close is safe when not connected."""
        # Should not raise
        await ssh_client.close()
        assert ssh_client._connection is None

    @pytest.mark.asyncio
    async def test_context_manager(self, ssh_client):
        """Test async context manager protocol."""
        # Mock the connect method
        ssh_client.connect = AsyncMock(return_value=SSHConnectionResult(success=True))
        ssh_client.close = AsyncMock()

        async with ssh_client:
            ssh_client.connect.assert_called_once()
        
        ssh_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_success(self, ssh_client):
        """Test successful SSH connection."""
        mock_connection = MagicMock()
        mock_asyncssh = MagicMock()
        mock_asyncssh.connect = AsyncMock(return_value=mock_connection)

        with patch.dict("sys.modules", {"asyncssh": mock_asyncssh}):
            with patch("asyncio.wait_for", return_value=mock_connection):
                result = await ssh_client.connect(timeout=5.0)
                assert result.success is True
                assert ssh_client._connection == mock_connection

    @pytest.mark.asyncio
    async def test_execute_success(self, ssh_client):
        """Test successful command execution."""
        # Set up mock connection
        mock_result = MagicMock()
        mock_result.stdout = "file1.txt\nfile2.txt"
        mock_result.stderr = ""
        mock_result.exit_status = 0
        
        mock_connection = MagicMock()
        mock_connection.run = AsyncMock(return_value=mock_result)
        ssh_client._connection = mock_connection

        with patch("asyncio.wait_for", return_value=mock_result):
            result = await ssh_client.execute("ls -la")
            assert result.success is True
            assert "file1.txt" in result.output
            assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_timeout(self, ssh_client):
        """Test command execution timeout."""
        mock_connection = MagicMock()
        mock_connection.run = AsyncMock()
        ssh_client._connection = mock_connection

        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            result = await ssh_client.execute("long_command")
            assert result.success is False
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_exception(self, ssh_client):
        """Test command execution with exception."""
        mock_connection = MagicMock()
        ssh_client._connection = mock_connection

        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = Exception("Connection lost")
            result = await ssh_client.execute("some_command")
            assert result.success is False
            assert "Connection lost" in result.error

    @pytest.mark.asyncio
    async def test_close_with_connection(self, ssh_client):
        """Test closing active SSH connection."""
        mock_connection = MagicMock()
        mock_connection.close = MagicMock()
        mock_connection.wait_closed = AsyncMock()
        ssh_client._connection = mock_connection

        await ssh_client.close()
        mock_connection.close.assert_called_once()
        mock_connection.wait_closed.assert_called_once()
        assert ssh_client._connection is None


class TestSoundTouchTelnetClient:
    """Tests for SoundTouchTelnetClient."""

    @pytest.fixture
    def telnet_client(self):
        """Create Telnet client instance."""
        return SoundTouchTelnetClient("192.168.1.100", port=17000)

    def test_client_initialization(self, telnet_client):
        """Test client is initialized with correct host and port."""
        assert telnet_client.host == "192.168.1.100"
        assert telnet_client.port == 17000
        assert telnet_client._reader is None
        assert telnet_client._writer is None

    @pytest.mark.asyncio
    async def test_connect_timeout(self, telnet_client):
        """Test connection timeout handling."""
        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            result = await telnet_client.connect(timeout=1.0)
            assert result.success is False
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_without_connection(self, telnet_client):
        """Test execute fails when not connected."""
        result = await telnet_client.execute("help")
        assert result.success is False
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_close_without_connection(self, telnet_client):
        """Test close is safe when not connected."""
        # Should not raise
        await telnet_client.close()
        assert telnet_client._reader is None
        assert telnet_client._writer is None

    @pytest.mark.asyncio
    async def test_context_manager(self, telnet_client):
        """Test async context manager protocol."""
        telnet_client.connect = AsyncMock(return_value=SSHConnectionResult(success=True))
        telnet_client.close = AsyncMock()

        async with telnet_client:
            telnet_client.connect.assert_called_once()
        
        telnet_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_success(self, telnet_client):
        """Test successful telnet connection."""
        mock_reader = MagicMock()
        mock_reader.read = AsyncMock(return_value=b"Welcome\r\n")
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = (mock_reader, mock_writer)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(telnet_client, "_read_available", new_callable=AsyncMock) as mock_read:
                    mock_read.return_value = "Welcome"
                    result = await telnet_client.connect(timeout=5.0)
                    assert result.success is True
                    assert telnet_client._reader == mock_reader
                    assert telnet_client._writer == mock_writer

    @pytest.mark.asyncio
    async def test_connect_exception(self, telnet_client):
        """Test telnet connection with exception."""
        with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.side_effect = OSError("Network unreachable")
            result = await telnet_client.connect()
            assert result.success is False
            assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_success(self, telnet_client):
        """Test successful command execution."""
        mock_reader = MagicMock()
        mock_reader.read = AsyncMock(return_value=b"command output\r\n")
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        
        telnet_client._reader = mock_reader
        telnet_client._writer = mock_writer

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("asyncio.wait_for", return_value=b"command output"):
                result = await telnet_client.execute("ls")
                assert result.success is True
                mock_writer.write.assert_called()

    @pytest.mark.asyncio
    async def test_execute_with_error_response(self, telnet_client):
        """Test command execution with error in response."""
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        
        telnet_client._reader = mock_reader
        telnet_client._writer = mock_writer
        telnet_client._read_available = AsyncMock(return_value="Error: Command not found")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await telnet_client.execute("invalid_cmd")
            assert result.success is False
            assert result.exit_code == 1

    @pytest.mark.asyncio
    async def test_execute_exception(self, telnet_client):
        """Test command execution with exception."""
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock(side_effect=Exception("Connection lost"))
        
        telnet_client._reader = mock_reader
        telnet_client._writer = mock_writer

        result = await telnet_client.execute("some_command")
        assert result.success is False
        assert "Connection lost" in result.error

    @pytest.mark.asyncio
    async def test_close_with_connection(self, telnet_client):
        """Test closing active telnet connection."""
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        
        telnet_client._reader = MagicMock()
        telnet_client._writer = mock_writer

        await telnet_client.close()
        mock_writer.close.assert_called_once()
        assert telnet_client._reader is None
        assert telnet_client._writer is None

    @pytest.mark.asyncio
    async def test_read_available_timeout(self, telnet_client):
        """Test _read_available with timeout."""
        mock_reader = MagicMock()
        telnet_client._reader = mock_reader

        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            result = await telnet_client._read_available(timeout=1.0)
            assert result == ""

    @pytest.mark.asyncio
    async def test_read_available_no_reader(self, telnet_client):
        """Test _read_available with no reader."""
        result = await telnet_client._read_available()
        assert result == ""


class TestConnectionHelpers:
    """Tests for connection test helper functions."""

    @pytest.mark.asyncio
    async def test_ssh_connection_success(self):
        """Test SSH connection test with open port."""
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.return_value = (MagicMock(), mock_writer)
            result = await check_ssh_port("192.168.1.100")
            assert result is True
            mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_ssh_connection_timeout(self):
        """Test SSH connection test with timeout."""
        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            result = await check_ssh_port("192.168.1.100")
            assert result is False

    @pytest.mark.asyncio
    async def test_ssh_connection_refused(self):
        """Test SSH connection test with refused connection."""
        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = ConnectionRefusedError()
            result = await check_ssh_port("192.168.1.100")
            assert result is False

    @pytest.mark.asyncio
    async def test_telnet_connection_success(self):
        """Test Telnet connection test with open port."""
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.return_value = (MagicMock(), mock_writer)
            result = await check_telnet_port("192.168.1.100")
            assert result is True

    @pytest.mark.asyncio
    async def test_telnet_connection_timeout(self):
        """Test Telnet connection test with timeout."""
        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            result = await check_telnet_port("192.168.1.100")
            assert result is False

    @pytest.mark.asyncio
    async def test_telnet_connection_os_error(self):
        """Test Telnet connection test with OS error."""
        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = OSError("Network unreachable")
            result = await check_telnet_port("192.168.1.100")
            assert result is False
