"""Tests for rename_device_via_ssh().

Covers:
- Happy path: reads XML, replaces DeviceName, writes back
- File not found / empty output
- DeviceName tag not found
- Write failure
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.devices.rename_service import rename_device_via_ssh


@dataclass
class FakeCommandResult:
    success: bool
    output: str = ""
    error: Optional[str] = None


class FakeSSH:
    """Fake SSH client for testing."""

    def __init__(self):
        self.execute = AsyncMock()
        self.commands: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def fake_ssh():
    return FakeSSH()


SAMPLE_XML = (
    '<?xml version="1.0"?>\n'
    "<SystemConfiguration>\n"
    "  <DeviceName>Old Name</DeviceName>\n"
    "  <Language>en</Language>\n"
    "</SystemConfiguration>"
)


class TestRenameDeviceViaSSH:
    """Tests for rename_device_via_ssh()."""

    @pytest.mark.asyncio
    async def test_happy_path(self, fake_ssh, monkeypatch):
        """Reads XML, replaces DeviceName tag, writes back."""
        fake_ssh.execute = AsyncMock(
            side_effect=[
                FakeCommandResult(success=True, output=SAMPLE_XML),  # cat
                FakeCommandResult(success=True),  # mount rw
                FakeCommandResult(success=True),  # write
                FakeCommandResult(success=True),  # mount ro
            ]
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        await rename_device_via_ssh("192.168.1.10", "New Name")

        assert fake_ssh.execute.call_count == 4
        write_call = fake_ssh.execute.call_args_list[2][0][0]
        assert "<DeviceName>New Name</DeviceName>" in write_call

    @pytest.mark.asyncio
    async def test_xml_escaping(self, fake_ssh, monkeypatch):
        """User-supplied name with special XML chars is escaped."""
        fake_ssh.execute = AsyncMock(
            side_effect=[
                FakeCommandResult(success=True, output=SAMPLE_XML),
                FakeCommandResult(success=True),
                FakeCommandResult(success=True),
                FakeCommandResult(success=True),
            ]
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        await rename_device_via_ssh("192.168.1.10", "Tom & Jerry <3>")

        write_call = fake_ssh.execute.call_args_list[2][0][0]
        assert "<DeviceName>Tom &amp; Jerry &lt;3&gt;</DeviceName>" in write_call

    @pytest.mark.asyncio
    async def test_file_not_found(self, fake_ssh, monkeypatch):
        """Raises RuntimeError when config file cannot be read."""
        fake_ssh.execute = AsyncMock(
            return_value=FakeCommandResult(success=False, output="")
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        with pytest.raises(RuntimeError, match="Could not read"):
            await rename_device_via_ssh("192.168.1.10", "New")

    @pytest.mark.asyncio
    async def test_empty_output(self, fake_ssh, monkeypatch):
        """Raises RuntimeError when config file is empty."""
        fake_ssh.execute = AsyncMock(
            return_value=FakeCommandResult(success=True, output="")
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        with pytest.raises(RuntimeError, match="Could not read"):
            await rename_device_via_ssh("192.168.1.10", "New")

    @pytest.mark.asyncio
    async def test_device_name_tag_not_found(self, fake_ssh, monkeypatch):
        """Raises RuntimeError when <DeviceName> tag is missing."""
        xml_no_tag = (
            "<SystemConfiguration><Language>en</Language></SystemConfiguration>"
        )
        fake_ssh.execute = AsyncMock(
            return_value=FakeCommandResult(success=True, output=xml_no_tag)
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        with pytest.raises(RuntimeError, match="<DeviceName> tag not found"):
            await rename_device_via_ssh("192.168.1.10", "New")

    @pytest.mark.asyncio
    async def test_write_failure(self, fake_ssh, monkeypatch):
        """Raises RuntimeError when writing config file fails."""
        fake_ssh.execute = AsyncMock(
            side_effect=[
                FakeCommandResult(success=True, output=SAMPLE_XML),  # cat
                FakeCommandResult(success=True),  # mount rw
                FakeCommandResult(success=False, error="Permission denied"),  # write
                FakeCommandResult(success=True),  # mount ro (in finally)
            ]
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        with pytest.raises(RuntimeError, match="Failed to write"):
            await rename_device_via_ssh("192.168.1.10", "New")

    @pytest.mark.asyncio
    async def test_remount_ro_after_write_failure(self, fake_ssh, monkeypatch):
        """Filesystem is remounted read-only even if write fails."""
        fake_ssh.execute = AsyncMock(
            side_effect=[
                FakeCommandResult(success=True, output=SAMPLE_XML),
                FakeCommandResult(success=True),  # mount rw
                FakeCommandResult(success=False, error="fail"),  # write
                FakeCommandResult(success=True),  # mount ro
            ]
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        with pytest.raises(RuntimeError):
            await rename_device_via_ssh("192.168.1.10", "New")

        # mount ro must be called (last call)
        last_call = fake_ssh.execute.call_args_list[-1][0][0]
        assert "remount,ro" in last_call


def _fake_ctx(fake_ssh):
    """Return a fake async context manager factory matching ssh_operation signature."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx(device_ip, operation_name):
        yield fake_ssh

    return _ctx
