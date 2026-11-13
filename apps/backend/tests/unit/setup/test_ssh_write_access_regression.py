"""Regression tests for the read-only partition problem found in the final browser audit (F13).

On a SoundTouch the persistent partition ``/mnt/nv`` (and ``/``) can be mounted read-only. Every write
used to fail with "Read-only file system". Writes now run inside ``write_access()`` /
``ssh_operation(write=True)``, which must

* remount ONLY the mount points that are read-only (never one that is already writable),
* put back read-only ONLY the mount points it changed itself (never a different one),
* never touch any other mount point (e.g. the USB stick),
* restore the previous mode in reverse order, also when the block raises, and
* leave the device exactly as it was found.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from opencloudtouch.core.exceptions import SSHOperationError
from opencloudtouch.setup import wizard_helpers
from opencloudtouch.setup.ssh_client import (
    CommandResult,
    SSHConnectionResult,
    SoundTouchSSHClient,
)


class FakeDevice:
    """Records every command and simulates /proc/mounts with live remount behaviour."""

    def __init__(
        self, options: dict[str, str], failing_remounts: set[str] | None = None
    ):
        self.options = dict(options)
        self.commands: list[str] = []
        self.failing_remounts = failing_remounts or set()

    async def execute(self, command: str, timeout: float = 30.0) -> CommandResult:
        self.commands.append(command)
        if "/proc/mounts" in command:
            for mount_point, opts in self.options.items():
                if f"m={mount_point} " in command:
                    return CommandResult(success=True, output=opts + "\n", exit_code=0)
            return CommandResult(success=True, output="\n", exit_code=0)
        if command.startswith("mount -o remount,"):
            mode, mount_point = command[len("mount -o remount,") :].split(" ", 1)
            if mount_point in self.failing_remounts and mode == "rw":
                return CommandResult(
                    success=False, output="", exit_code=1, error="busy"
                )
            self.options[mount_point] = mode + ",relatime"
            return CommandResult(success=True, output="", exit_code=0)
        return CommandResult(success=True, output="", exit_code=0)

    @property
    def remounts(self) -> list[str]:
        return [c for c in self.commands if "remount" in c]


def _client(device: FakeDevice) -> SoundTouchSSHClient:
    client = SoundTouchSSHClient("10.0.0.5")
    client.execute = device.execute  # type: ignore[method-assign]
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start, expected_remounts",
    [
        # only /mnt/nv is read-only: only /mnt/nv is changed and restored
        (
            {"/": "rw,relatime", "/mnt/nv": "ro,relatime"},
            ["mount -o remount,rw /mnt/nv", "mount -o remount,ro /mnt/nv"],
        ),
        # only / is read-only: only / is changed and restored
        (
            {"/": "ro,relatime", "/mnt/nv": "rw,relatime"},
            ["mount -o remount,rw /", "mount -o remount,ro /"],
        ),
        # both read-only: both changed, restored in reverse order
        (
            {"/": "ro,relatime", "/mnt/nv": "ro,relatime"},
            [
                "mount -o remount,rw /",
                "mount -o remount,rw /mnt/nv",
                "mount -o remount,ro /mnt/nv",
                "mount -o remount,ro /",
            ],
        ),
        # both writable: nothing is touched at all
        ({"/": "rw,relatime", "/mnt/nv": "rw,relatime"}, []),
    ],
)
async def test_only_changed_mounts_are_restored(start, expected_remounts):
    device = FakeDevice(start)

    async with _client(device).write_access():
        pass

    assert device.remounts == expected_remounts
    # the device ends exactly as it started
    for mount_point, options in start.items():
        assert device.options[mount_point].split(",")[0] == options.split(",")[0]


@pytest.mark.asyncio
async def test_a_writable_mount_is_never_set_read_only():
    """The bug to avoid: locking a partition the block did not unlock."""
    device = FakeDevice({"/": "rw,relatime", "/mnt/nv": "ro,relatime"})

    async with _client(device).write_access():
        pass

    assert "mount -o remount,ro /" not in device.commands
    assert device.options["/"].startswith("rw")


@pytest.mark.asyncio
async def test_other_mount_points_are_never_touched():
    device = FakeDevice(
        {"/": "ro", "/mnt/nv": "ro", "/media/sda1": "rw", "/mnt/update": "ro"}
    )

    async with _client(device).write_access():
        pass

    assert all(
        "/media/sda1" not in c and "/mnt/update" not in c for c in device.remounts
    )
    assert device.options["/mnt/update"] == "ro"  # not unlocked, not changed


@pytest.mark.asyncio
async def test_writes_happen_while_unlocked_and_never_after_the_restore():
    device = FakeDevice({"/": "rw", "/mnt/nv": "ro"})

    async with _client(device).write_access():
        device.commands.append("<write>")
        assert device.options["/mnt/nv"].startswith("rw")

    assert device.commands.index("mount -o remount,rw /mnt/nv") < device.commands.index(
        "<write>"
    )
    assert device.commands.index("<write>") < device.commands.index(
        "mount -o remount,ro /mnt/nv"
    )
    assert device.options["/mnt/nv"].startswith("ro")


@pytest.mark.asyncio
async def test_failed_unlock_is_not_reported_as_changed_and_not_locked_again():
    device = FakeDevice({"/": "rw", "/mnt/nv": "ro"}, failing_remounts={"/mnt/nv"})

    async with _client(device).write_access():
        pass

    assert "mount -o remount,ro /mnt/nv" not in device.commands


@pytest.mark.asyncio
async def test_restore_runs_when_the_block_raises():
    device = FakeDevice({"/": "ro", "/mnt/nv": "ro"})

    async def failing_block():
        async with _client(device).write_access():
            raise ValueError("write failed")

    with pytest.raises(ValueError):
        await failing_block()

    assert device.options["/"].startswith("ro")
    assert device.options["/mnt/nv"].startswith("ro")
    assert device.remounts[-2:] == [
        "mount -o remount,ro /mnt/nv",
        "mount -o remount,ro /",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options, expected",
    [
        ("ro,relatime", True),
        ("rw,relatime", False),
        ("rw,relatime,errors=remount-ro", False),  # "remount-ro" is not read-only
        ("relatime,ro", True),
        ("rw,noatime,data=ordered", False),
    ],
)
async def test_read_only_detection_matches_whole_options_only(options, expected):
    device = FakeDevice({"/mnt/nv": options})
    assert await _client(device).is_mount_read_only("/mnt/nv") is expected


@pytest.mark.asyncio
async def test_unknown_mount_is_neither_changed_nor_restored():
    device = FakeDevice({})

    async with _client(device).write_access(("/does/not/exist",)):
        pass

    assert device.remounts == []
    assert await _client(device).is_mount_read_only("/does/not/exist") is None


@pytest.mark.asyncio
async def test_nested_blocks_restore_only_what_each_block_changed():
    device = FakeDevice({"/": "rw", "/mnt/nv": "ro"})
    client = _client(device)

    async with client.write_access():
        async with client.write_access():  # nv is rw now: the inner block must not touch it
            pass
        assert device.options["/mnt/nv"].startswith("rw")

    assert device.remounts == [
        "mount -o remount,rw /mnt/nv",
        "mount -o remount,ro /mnt/nv",
    ]


# --- coupling to the SSH login: ssh_operation(write=True) ----------------------------


def _patch_login(device: FakeDevice):
    client = SoundTouchSSHClient("10.0.0.5")
    client.execute = device.execute  # type: ignore[method-assign]

    async def connect(timeout: float = 10.0):
        return SSHConnectionResult(success=True, output="Connected")

    async def close():
        device.commands.append("<close>")

    client.connect = connect  # type: ignore[method-assign]
    client.close = close  # type: ignore[method-assign]
    return patch.object(wizard_helpers, "SoundTouchSSHClient", return_value=client)


@pytest.mark.asyncio
async def test_ssh_operation_write_unlocks_and_restores_around_the_body():
    device = FakeDevice({"/": "ro", "/mnt/nv": "ro"})

    with _patch_login(device):
        async with wizard_helpers.ssh_operation(
            "10.0.0.5", "modify-config", write=True
        ) as ssh:
            await ssh.execute("touch /mnt/nv/remote_services")

    sequence = [
        c
        for c in device.commands
        if "remount" in c or c.startswith("touch") or c == "<close>"
    ]
    assert sequence == [
        "mount -o remount,rw /",
        "mount -o remount,rw /mnt/nv",
        "touch /mnt/nv/remote_services",
        "mount -o remount,ro /mnt/nv",
        "mount -o remount,ro /",
        "<close>",
    ]


@pytest.mark.asyncio
async def test_ssh_operation_without_write_never_remounts():
    device = FakeDevice({"/": "ro", "/mnt/nv": "ro"})

    with _patch_login(device):
        async with wizard_helpers.ssh_operation("10.0.0.5", "verify-setup") as ssh:
            await ssh.execute("cat /etc/hosts")

    assert device.remounts == []
    assert not any("/proc/mounts" in c for c in device.commands)


@pytest.mark.asyncio
async def test_ssh_operation_restores_the_mode_when_the_operation_fails():
    device = FakeDevice({"/": "rw", "/mnt/nv": "ro"})

    with _patch_login(device):

        async def failing_operation():
            async with wizard_helpers.ssh_operation("10.0.0.5", "finalize", write=True):
                raise RuntimeError("boom")

        with pytest.raises(SSHOperationError):
            await failing_operation()

    assert device.options["/mnt/nv"].startswith("ro")
    assert device.options["/"].startswith("rw")
    assert "mount -o remount,ro /" not in device.commands


@pytest.mark.asyncio
async def test_every_write_operation_asks_for_write_access():
    """A write operation that forgets write=True would fail on a read-only device again."""
    import pathlib
    import re

    root = pathlib.Path(wizard_helpers.__file__).parent.parent
    expected = {
        "setup/wizard/step5_config.py": "modify-config",
        "setup/wizard/step6_hosts.py": "modify-hosts",
        "setup/wizard/ntp_patch.py": "patch-ntp",
        "setup/wizard/step8_finalize_verify.py": "finalize",
        "setup/restore_service.py": "restore",
    }
    for rel, operation in expected.items():
        source = (root / rel).read_text(encoding="utf-8")
        assert re.search(
            rf'ssh_operation\([^)]*"{operation}",\s*write=True', source
        ), rel

    routes = (root / "setup/routes.py").read_text(encoding="utf-8")
    assert "ssh_client.write_access()" in routes
