"""Unit tests for StartupCheck service."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from opencloudtouch.devices.repository import Device
from opencloudtouch.devices.startup_check import StartupCheck
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT

INFO_XML_CONFIGURED = """\
<?xml version="1.0" encoding="UTF-8" ?>
<info deviceID="689E194F7D2F">
  <name>SoundTouch 20</name>
  <type>SoundTouch 20</type>
  <margeAccountUUID>5448503</margeAccountUUID>
  <components/>
  <margeURL>http://content.api.bose.io:7777</margeURL>
</info>"""

INFO_XML_UNCONFIGURED = """\
<?xml version="1.0" encoding="UTF-8" ?>
<info deviceID="689E194F7D2F">
  <name>SoundTouch 20</name>
  <type>SoundTouch 20</type>
  <components/>
  <margeURL>https://streaming.bose.com</margeURL>
</info>"""


def _make_device(
    device_id: str = "689E194F7D2F",
    ip: str = "192.168.1.100",
    name: str = "SoundTouch 20",
    setup_status: str = "unknown",
) -> Device:
    return Device(
        device_id=device_id,
        ip=ip,
        name=name,
        model="SoundTouch 20",
        mac_address="68:9E:19:4F:7D:2F",
        firmware_version="29.0.6",
        setup_status=setup_status,
    )


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.update_setup_status = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_startup_check_marks_configured_device(mock_repo):
    """Device with margeURL containing content.api.bose.io → configured."""
    device = _make_device(setup_status="unknown")
    mock_repo.get_all.return_value = [device]

    with respx.mock:
        respx.get(f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}/info").mock(
            return_value=httpx.Response(200, text=INFO_XML_CONFIGURED)
        )
        checker = StartupCheck(mock_repo)
        await checker.run()

    mock_repo.update_setup_status.assert_called_once()
    call_kwargs = mock_repo.update_setup_status.call_args
    assert call_kwargs.kwargs["device_id"] == device.device_id
    assert call_kwargs.kwargs["setup_status"] == "configured"
    assert call_kwargs.kwargs["setup_completed_at"] is not None


@pytest.mark.asyncio
async def test_startup_check_marks_unconfigured_device(mock_repo):
    """Device with margeURL = streaming.bose.com → unconfigured."""
    device = _make_device(setup_status="unknown")
    mock_repo.get_all.return_value = [device]

    with respx.mock:
        respx.get(f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}/info").mock(
            return_value=httpx.Response(200, text=INFO_XML_UNCONFIGURED)
        )
        checker = StartupCheck(mock_repo)
        await checker.run()

    mock_repo.update_setup_status.assert_called_once()
    call_kwargs = mock_repo.update_setup_status.call_args
    assert call_kwargs.kwargs["setup_status"] == "unconfigured"
    assert call_kwargs.kwargs["setup_completed_at"] is None


@pytest.mark.asyncio
async def test_startup_check_skips_offline_device(mock_repo):
    """Unreachable device → status stays 'unknown', no update."""
    device = _make_device(setup_status="unknown")
    mock_repo.get_all.return_value = [device]

    with respx.mock:
        respx.get(f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}/info").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        checker = StartupCheck(mock_repo)
        await checker.run()

    mock_repo.update_setup_status.assert_not_called()


@pytest.mark.asyncio
async def test_startup_check_skips_already_configured(mock_repo):
    """Device with setup_status='configured' is NOT checked."""
    device = _make_device(setup_status="configured")
    mock_repo.get_all.return_value = [device]

    checker = StartupCheck(mock_repo)
    await checker.run()

    mock_repo.update_setup_status.assert_not_called()


@pytest.mark.asyncio
async def test_startup_check_sets_completed_at(mock_repo):
    """When marking configured, setup_completed_at is set to current time."""
    device = _make_device(setup_status="unknown")
    mock_repo.get_all.return_value = [device]

    before = datetime.now(UTC)

    with respx.mock:
        respx.get(f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}/info").mock(
            return_value=httpx.Response(200, text=INFO_XML_CONFIGURED)
        )
        checker = StartupCheck(mock_repo)
        await checker.run()

    after = datetime.now(UTC)

    call_kwargs = mock_repo.update_setup_status.call_args
    completed_at = call_kwargs.kwargs["setup_completed_at"]
    assert completed_at is not None
    assert before <= completed_at <= after


@pytest.mark.asyncio
async def test_startup_check_skips_device_without_ip(mock_repo):
    """Device with ip=None is skipped entirely."""
    device = _make_device(setup_status="unknown")
    device.ip = None
    mock_repo.get_all.return_value = [device]

    checker = StartupCheck(mock_repo)
    await checker.run()

    mock_repo.update_setup_status.assert_not_called()


@pytest.mark.asyncio
async def test_startup_check_handles_malformed_xml(mock_repo):
    """Malformed XML response → device stays unknown, no crash."""
    device = _make_device(setup_status="unknown")
    mock_repo.get_all.return_value = [device]

    with respx.mock:
        respx.get(f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}/info").mock(
            return_value=httpx.Response(200, text="<not>valid xml<")
        )
        checker = StartupCheck(mock_repo)
        await checker.run()

    mock_repo.update_setup_status.assert_not_called()
