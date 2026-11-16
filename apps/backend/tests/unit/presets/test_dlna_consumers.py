"""Every reader of ``station_url`` must treat a DLNA preset as not streamable (AC-B14)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import (
    get_device_state_manager,
    get_preset_service,
)
from opencloudtouch.core.dlna_reference import DlnaReference, to_station_url
from opencloudtouch.devices.api.routes import get_now_playing
from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.main import _find_preset_value
from opencloudtouch.presets.api.descriptor_service import StationDescriptorService
from opencloudtouch.presets.models import Preset

DLNA = Preset(
    device_id="D",
    preset_number=1,
    station_uuid="dlna-0123456789abcdef",
    station_name="Song",
    station_url=to_station_url(DlnaReference("udn", "obj")),
    source="DLNA",
)


@pytest.fixture
def service():
    from opencloudtouch.main import app

    svc = AsyncMock()
    svc.get_preset = AsyncMock(return_value=DLNA)
    svc._validate_stream_url = AsyncMock()
    app.dependency_overrides[get_preset_service] = lambda: svc
    app.dependency_overrides[get_device_state_manager] = lambda: DeviceStateManager()
    yield svc
    app.dependency_overrides.clear()


@pytest.fixture
def client(service):
    from opencloudtouch.main import app

    return TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/playlist/D/1.m3u",
        "/playlist/D/1.pls",
        "/device/D/preset/1",
        "/descriptor/device/D/preset/1",
    ],
)
def test_streaming_routes_answer_409_without_fetching(client, service, path):
    r = client.get(path, follow_redirects=False)
    assert (r.status_code, r.json()["code"]) == (409, "dlna_preset_not_streamable")
    service._validate_stream_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_descriptor_service_returns_none():
    svc = AsyncMock()
    svc.get_preset = AsyncMock(return_value=DLNA)
    assert await StationDescriptorService(svc).get_descriptor("D", 1) is None


def test_find_preset_value_ignores_dlna_stream_url():
    assert _find_preset_value([DLNA], "Song", "station_url") is None
    assert _find_preset_value([DLNA], "Song", "station_favicon") is None  # unset


@pytest.mark.asyncio
async def test_now_playing_skips_icy_for_dlna():
    info = NowPlayingInfo(source="INTERNET_RADIO", state="PLAY_STATE", station_name="Song")
    devices = MagicMock()
    devices.get_now_playing = AsyncMock(return_value=info)
    presets = AsyncMock()
    presets.get_all_presets = AsyncMock(return_value=[DLNA])
    with patch(
        "opencloudtouch.devices.api.routes._enrich_from_icy", new=AsyncMock()
    ) as icy:
        await get_now_playing("D", devices, presets, DeviceStateManager())
    icy.assert_not_awaited()
