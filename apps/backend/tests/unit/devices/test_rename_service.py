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
from xml.sax.saxutils import escape as xml_escape

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
                FakeCommandResult(success=True),  # write
            ]
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        await rename_device_via_ssh("192.168.1.10", "New Name")

        assert fake_ssh.execute.call_count == 2
        write_call = fake_ssh.execute.call_args_list[1][0][0]
        assert "<DeviceName>New Name</DeviceName>" in write_call

    @pytest.mark.asyncio
    async def test_xml_escaping(self, fake_ssh, monkeypatch):
        """User-supplied name with special XML chars is escaped."""
        fake_ssh.execute = AsyncMock(
            side_effect=[
                FakeCommandResult(success=True, output=SAMPLE_XML),
                FakeCommandResult(success=True),
            ]
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        await rename_device_via_ssh("192.168.1.10", "Tom & Jerry <3>")

        write_call = fake_ssh.execute.call_args_list[1][0][0]
        assert "<DeviceName>Tom &amp; Jerry &lt;3&gt;</DeviceName>" in write_call

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name", [r"A\1", r"\g<0>", r"a\q", r"back\slash"])
    async def test_backslashes_are_written_literally(self, fake_ssh, monkeypatch, name):
        """A backslash in the name must not be read as a regex group reference."""
        fake_ssh.execute = AsyncMock(
            side_effect=[
                FakeCommandResult(success=True, output=SAMPLE_XML),
                FakeCommandResult(success=True),
            ]
        )
        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        await rename_device_via_ssh("192.168.1.10", name)

        write_call = fake_ssh.execute.call_args_list[1][0][0]
        assert f"<DeviceName>{xml_escape(name)}</DeviceName>" in write_call
        assert write_call.count("<DeviceName>") == 1

    @pytest.mark.asyncio
    async def test_config_is_replaced_only_after_the_new_file_is_complete(
        self, fake_ssh, monkeypatch
    ):
        """The new XML goes to a temporary file and is moved over the original in the same command.

        Writing the original directly truncates it first, so a dropped connection mid-write left a broken
        SystemConfigurationDB.xml on the device.
        """
        fake_ssh.execute = AsyncMock(
            side_effect=[
                FakeCommandResult(success=True, output=SAMPLE_XML),
                FakeCommandResult(success=True),
            ]
        )
        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        await rename_device_via_ssh("192.168.1.10", "New Name")

        write_call = fake_ssh.execute.call_args_list[1][0][0]
        target = "/mnt/nv/BoseApp-Persistence/1/SystemConfigurationDB.xml"
        assert f"cat > {target} " not in write_call
        assert "&& mv " in write_call

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name", ["two\nlines", "bell\x07", "XMLEOF\rx", "nul\x00"])
    async def test_control_characters_are_rejected_before_any_command(
        self, fake_ssh, monkeypatch, name
    ):
        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        with pytest.raises(ValueError, match="control characters"):
            await rename_device_via_ssh("192.168.1.10", name)

        fake_ssh.execute.assert_not_called()

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
                FakeCommandResult(success=False, error="Permission denied"),  # write
            ]
        )

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh),
        )

        with pytest.raises(RuntimeError, match="Failed to write"):
            await rename_device_via_ssh("192.168.1.10", "New")

    @pytest.mark.asyncio
    async def test_requests_write_access(self, fake_ssh, monkeypatch):
        """The rename runs inside ssh_operation(write=True) so the partitions are writable."""
        fake_ssh.execute = AsyncMock(
            side_effect=[
                FakeCommandResult(success=True, output=SAMPLE_XML),
                FakeCommandResult(success=True),
            ]
        )
        seen = {}

        monkeypatch.setattr(
            "opencloudtouch.devices.rename_service.ssh_operation",
            _fake_ctx(fake_ssh, seen),
        )

        await rename_device_via_ssh("192.168.1.10", "New")

        assert seen["write"] is True


def _fake_ctx(fake_ssh, seen=None):
    """Return a fake async context manager factory matching ssh_operation signature."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx(device_ip, operation_name, write=False):
        if seen is not None:
            seen["write"] = write
        yield fake_ssh

    return _ctx
