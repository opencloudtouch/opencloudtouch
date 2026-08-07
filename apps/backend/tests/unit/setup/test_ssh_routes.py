"""Tests for setup/routes.py SSH endpoints -- Issue #407.

`enable_permanent_ssh` copies remote_services to the device over SSH and
reports success, but never persisted that outcome to the device repository.
As a result `ssh_permanent` stayed `False` forever, which in turn made
`health_check._ssh_verify_all()` skip the periodic SSH/BMX verification for
every device (see devices/health_check.py).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.devices.repository import Device
from opencloudtouch.setup.api_models import EnablePermanentSSHRequest
from opencloudtouch.setup.routes import enable_permanent_ssh
from opencloudtouch.setup.ssh_client import CommandResult, SSHConnectionResult


def _make_device_repo(device: Device | None):
    repo = AsyncMock()
    repo.get_by_device_id = AsyncMock(return_value=device)
    repo.update_setup_status = AsyncMock()
    return repo


def _make_ssh_client_cls(connect_success=True, command_success=True):
    """Patch target for opencloudtouch.setup.routes.SoundTouchSSHClient."""
    instance = MagicMock()
    instance.connect = AsyncMock(
        return_value=SSHConnectionResult(success=connect_success)
    )
    instance.execute = AsyncMock(
        return_value=CommandResult(success=command_success, output="")
    )
    instance.close = AsyncMock()
    cls = MagicMock(return_value=instance)
    return cls


@pytest.mark.asyncio
async def test_enable_permanent_ssh_persists_flag_to_repository():
    """A successful SSH enable must set ssh_permanent=True in the DB."""
    device = Device(
        device_id="ABC123",
        ip="192.168.1.50",
        name="Living Room",
        model="ST10",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="27.0.6",
        setup_status="configured",
        ssh_permanent=False,
    )
    device_repo = _make_device_repo(device)
    request = EnablePermanentSSHRequest(
        device_id="ABC123", ip="192.168.1.50", make_permanent=True
    )

    with patch(
        "opencloudtouch.setup.routes.SoundTouchSSHClient",
        _make_ssh_client_cls(),
    ):
        await enable_permanent_ssh(request, device_repo)

    device_repo.update_setup_status.assert_awaited_once_with(
        "ABC123", "configured", ssh_permanent=True
    )


@pytest.mark.asyncio
async def test_enable_permanent_ssh_skips_repository_update_when_device_unknown():
    """No DB row yet must not crash the endpoint -- SSH itself still succeeded."""
    device_repo = _make_device_repo(None)
    request = EnablePermanentSSHRequest(
        device_id="UNKNOWN", ip="192.168.1.51", make_permanent=True
    )

    with patch(
        "opencloudtouch.setup.routes.SoundTouchSSHClient",
        _make_ssh_client_cls(),
    ):
        result = await enable_permanent_ssh(request, device_repo)

    assert result["success"] is True
    device_repo.update_setup_status.assert_not_awaited()
