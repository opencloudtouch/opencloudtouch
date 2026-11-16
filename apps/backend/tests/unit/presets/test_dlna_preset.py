"""DLNA presets: marker, service, parser/sync (AC-B1, B3, B8, B11, B12, B16)."""

import base64
import json
import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.core.dlna_reference import (
    DlnaReference,
    DlnaReferenceTooLongError,
    build_orion_location,
    station_uuid,
    to_station_url,
)
from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.dlna.service import ResolvedDlnaItem
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.parser import DevicePresetParser
from opencloudtouch.presets.service import PresetService

REF = DlnaReference("udn-1", "a/b c")


def _preset(**kw) -> Preset:
    args = dict(
        device_id="D",
        preset_number=1,
        station_uuid="u",
        station_name="n",
        station_url="http://x/y",
        source="LOCAL_INTERNET_RADIO",
    )
    return Preset(**{**args, **kw})


def test_to_dict_dlna_marker_for_dlna_preset():
    p = _preset(source="DLNA", station_url=to_station_url(REF))
    assert p.to_dict()["dlna"] == {"server_id": "udn-1", "object_id": "a/b c"}


def test_to_dict_dlna_is_none_for_radio_and_unparsable(caplog):
    assert _preset().to_dict()["dlna"] is None
    assert _preset(source="DLNA", station_url="http://x").to_dict()["dlna"] is None
    assert "unparsable" in caplog.text


# --- service -----------------------------------------------------------------


@pytest.fixture
def parts(monkeypatch):
    monkeypatch.setenv("OCT_MOCK_MODE", "true")
    repo = AsyncMock()
    repo.set_preset = AsyncMock(side_effect=lambda p: p)
    devices = AsyncMock()
    devices.get_by_device_id = AsyncMock(return_value=MagicMock(ip="10.0.0.1"))
    dlna = AsyncMock()
    dlna.resolve_playable = AsyncMock(
        return_value=ResolvedDlnaItem("Title", "http://nas/a.mp3", "http://nas/c.jpg")
    )
    return PresetService(repo, devices), repo, devices, dlna


@pytest.mark.asyncio
async def test_set_dlna_preset_saves_reference(parts):
    service, repo, _, dlna = parts
    preset = await service.set_dlna_preset("D", 2, "udn-1", "a/b c", dlna)
    dlna.resolve_playable.assert_awaited_once()
    assert dlna.resolve_playable.await_args.kwargs["cache_only"] is False
    assert preset.source == "DLNA"
    assert re.fullmatch(r"dlna-[0-9a-f]{16}", preset.station_uuid)
    assert preset.station_uuid == station_uuid(REF)  # deterministic (AC-B3)
    assert preset.station_url == to_station_url(REF)
    assert (preset.station_name, preset.station_favicon) == (
        "Title",
        "http://nas/c.jpg",
    )
    repo.set_preset.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_dlna_preset_truncates_title(parts):
    service, _, _, dlna = parts
    dlna.resolve_playable.return_value = ResolvedDlnaItem("t" * 300, "http://a/b", None)
    preset = await service.set_dlna_preset("D", 1, "s", "o", dlna)
    assert len(preset.station_name) == 200


@pytest.mark.asyncio
async def test_set_dlna_preset_unknown_device(parts):
    service, repo, devices, dlna = parts
    devices.get_by_device_id.return_value = None
    with pytest.raises(DeviceNotFoundError):
        await service.set_dlna_preset("D", 1, "s", "o", dlna)
    repo.set_preset.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_dlna_preset_speaker_unreachable_saves_nothing(parts, monkeypatch):
    service, repo, _, dlna = parts
    client = AsyncMock()
    client.store_preset.side_effect = DeviceConnectionError("10.0.0.1", "down")
    monkeypatch.setattr(
        "opencloudtouch.devices.adapter.get_device_client", lambda url: client
    )
    with pytest.raises(DeviceConnectionError):
        await service.set_dlna_preset("D", 1, "s", "o", dlna)
    repo.set_preset.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_dlna_preset_too_long_saves_nothing(parts):
    service, repo, _, dlna = parts
    dlna.resolve_playable.return_value = ResolvedDlnaItem("ü" * 200, "http://a/b", None)
    with pytest.raises(DlnaReferenceTooLongError):
        await service.set_dlna_preset("D", 1, "udn-1", "ü" * 512, dlna)
    repo.set_preset.assert_not_awaited()


# --- parser / sync -----------------------------------------------------------


def _xml(location: str, name: str = "Song") -> bytes:
    return (
        f'<presets><preset id="3"><ContentItem source="LOCAL_INTERNET_RADIO" '
        f'type="stationurl" location="{location}"><itemName>{name}</itemName>'
        f"</ContentItem></preset></presets>"
    ).encode()


def test_parser_recognises_dlna_preset():
    location = build_orion_location("http://oct:7777", REF, "Song")
    (preset,) = DevicePresetParser().parse_presets("D", _xml(location))
    assert preset.source == "DLNA"
    assert preset.station_uuid == station_uuid(REF)
    assert preset.station_url == to_station_url(REF)
    assert preset.station_name == "Song"


def test_parser_still_skips_payload_without_stream_or_dlna():
    data = base64.urlsafe_b64encode(json.dumps({"name": "x"}).encode()).decode()
    location = f"http://oct:7777/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
    assert DevicePresetParser().parse_presets("D", _xml(location)) == []
