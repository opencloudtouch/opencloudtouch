"""Tests for SoundTouchSSHClient.write_access and ssh_operation(write=True)."""

from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.setup.ssh_client import CommandResult, SoundTouchSSHClient
from opencloudtouch.setup import wizard_helpers


def _client(mounts: dict[str, str]):
    """Client whose execute() answers the mount lookups and records every command."""
    client = SoundTouchSSHClient("10.0.0.5")
    calls: list[str] = []

    async def fake_execute(command: str, timeout: float = 30.0) -> CommandResult:
        calls.append(command)
        if "/proc/mounts" in command:
            for mount_point, options in mounts.items():
                if f"m={mount_point} " in command or f"m='{mount_point}' " in command:
                    return CommandResult(
                        success=True, output=options + "\n", exit_code=0
                    )
            return CommandResult(success=True, output="\n", exit_code=0)
        return CommandResult(success=True, output="", exit_code=0)

    client.execute = fake_execute  # type: ignore[method-assign]
    return client, calls


@pytest.mark.asyncio
async def test_read_only_mounts_are_remounted_and_restored():
    client, calls = _client({"/": "ro,relatime", "/mnt/nv": "ro,relatime"})

    async with client.write_access():
        calls.append("<write>")

    assert calls.index("mount -o remount,rw /") < calls.index("<write>")
    assert calls.index("mount -o remount,rw /mnt/nv") < calls.index("<write>")
    assert calls.index("<write>") < calls.index("mount -o remount,ro /mnt/nv")
    assert calls[-1] == "mount -o remount,ro /"


@pytest.mark.asyncio
async def test_already_writable_mounts_are_left_alone():
    client, calls = _client({"/": "rw,relatime", "/mnt/nv": "rw,relatime"})

    async with client.write_access():
        pass

    assert not any("remount" in c for c in calls)


@pytest.mark.asyncio
async def test_only_the_read_only_mount_is_changed_and_restored():
    client, calls = _client({"/": "rw,relatime", "/mnt/nv": "ro,relatime"})

    async with client.write_access():
        pass

    remounts = [c for c in calls if "remount" in c]
    assert remounts == ["mount -o remount,rw /mnt/nv", "mount -o remount,ro /mnt/nv"]


@pytest.mark.asyncio
async def test_mode_is_restored_when_the_block_raises():
    client, calls = _client({"/": "rw", "/mnt/nv": "ro"})

    async def failing_block():
        async with client.write_access():
            raise RuntimeError("write failed")

    with pytest.raises(RuntimeError):
        await failing_block()

    assert calls[-1] == "mount -o remount,ro /mnt/nv"


@pytest.mark.asyncio
async def test_unknown_mount_state_is_not_touched():
    client, calls = _client({})

    async with client.write_access():
        pass

    assert not any("remount" in c for c in calls)


@pytest.mark.asyncio
async def test_ssh_operation_write_flag_uses_write_access():
    fake = AsyncMock()
    fake.__aenter__.return_value = fake
    entered = []

    class _Ctx:
        async def __aenter__(self):
            entered.append("enter")

        async def __aexit__(self, *exc):
            entered.append("exit")
            return False

    fake.write_access = lambda: _Ctx()

    with patch.object(wizard_helpers, "SoundTouchSSHClient", return_value=fake):
        async with wizard_helpers.ssh_operation("10.0.0.5", "x", write=True):
            entered.append("body")
        async with wizard_helpers.ssh_operation("10.0.0.5", "y"):
            entered.append("read-only-body")

    assert entered == ["enter", "body", "exit", "read-only-body"]
