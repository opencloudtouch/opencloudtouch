"""Native STORED_MUSIC preset write: decision table, payload, suffix helpers (AC-C1..C6, C8)."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.core.dlna_reference import (
    native_location,
    strip_native_location,
)
from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.client import NativeContentItem
from opencloudtouch.devices.client_adapter import BoseDeviceClientAdapter
from opencloudtouch.dlna.service import ResolvedDlnaItem
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.parser import DevicePresetParser
from opencloudtouch.presets.service import PresetService

SERVER = "5f9ec1b3-ed59-4f22-9c2e-1d3a7b8c4e01"
ACCOUNT = f"{SERVER}/0"


@pytest.fixture
def parts(monkeypatch):
    monkeypatch.setenv("OCT_MOCK_MODE", "true")
    repo = AsyncMock()
    repo.set_preset = AsyncMock(side_effect=lambda p: p)
    devices = AsyncMock()
    devices.get_by_device_id = AsyncMock(return_value=MagicMock(ip="192.0.2.10"))
    dlna = AsyncMock()
    dlna.resolve_playable = AsyncMock(
        return_value=ResolvedDlnaItem(
            "Album <1>", "http://nas/a.mp3", "http://nas/c.jpg", is_container=True
        )
    )
    native = AsyncMock()
    native.native_ready = AsyncMock(return_value=True)
    client = AsyncMock()
    monkeypatch.setattr(
        "opencloudtouch.devices.adapter.get_device_client", lambda url: client
    )
    service = PresetService(repo, devices)
    service.native_service = native
    return service, repo, dlna, native, client


async def test_ready_container_writes_native_item(parts):
    service, repo, dlna, native, client = parts
    preset = await service.set_dlna_preset("D", 2, SERVER.upper(), "folder/1", dlna)

    kwargs = client.store_preset.await_args.kwargs
    assert kwargs["native_item"] == NativeContentItem(ACCOUNT, "folder/1", "dir")
    assert kwargs.get("dlna_reference") is None
    assert (preset.source, preset.native_type) == ("DLNA", "dir")
    assert preset.station_url.startswith(f"dlna://{SERVER}/")
    assert preset.to_dict()["dlna_playback"] == "native"
    assert preset.to_dict()["dlna"] == {"server_id": SERVER, "object_id": "folder/1"}
    native.native_ready.assert_awaited_once_with("D", SERVER.upper())


async def test_native_write_skips_the_orion_length_cap(parts):
    service, _, dlna, _, _ = parts
    preset = await service.set_dlna_preset("D", 1, SERVER, "ü" * 512, dlna)
    assert preset.native_type == "dir"


async def test_track_is_native_with_the_track_suffix(parts):
    service, _, dlna, _, client = parts
    dlna.resolve_playable.return_value = ResolvedDlnaItem("T", "http://nas/a.mp3", None)
    preset = await service.set_dlna_preset("D", 1, SERVER, "t1", dlna)

    assert client.store_preset.await_args.kwargs["native_item"] == NativeContentItem(
        ACCOUNT, "t1 TRACK", "track"
    )
    assert (preset.native_type, preset.to_dict()["dlna_playback"]) == (
        "track",
        "native",
    )


async def test_other_states_use_the_v1_write(parts):
    service, _, dlna, native, client = parts
    native.native_ready.return_value = False
    preset = await service.set_dlna_preset("D", 1, SERVER, "folder", dlna)

    assert "native_item" not in client.store_preset.await_args.kwargs
    assert client.store_preset.await_args.kwargs["dlna_reference"] is not None
    assert (preset.native_type, preset.to_dict()["dlna_playback"]) == (
        None,
        "reference",
    )


async def test_without_native_service_it_is_v1(parts):
    service, _, dlna, _, client = parts
    service.native_service = None
    await service.set_dlna_preset("D", 1, SERVER, "folder", dlna)
    assert "native_item" not in client.store_preset.await_args.kwargs


async def test_unreadable_speaker_saves_nothing(parts):
    service, repo, dlna, native, client = parts
    native.native_ready.side_effect = DeviceConnectionError("192.0.2.10", "down")
    with pytest.raises(DeviceConnectionError):
        await service.set_dlna_preset("D", 1, SERVER, "folder", dlna)
    client.store_preset.assert_not_awaited()
    repo.set_preset.assert_not_awaited()


async def test_failing_native_write_saves_nothing_and_logs_no_title(parts, caplog):
    service, repo, dlna, _, client = parts
    client.store_preset.side_effect = DeviceConnectionError("192.0.2.10", "down")
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(DeviceConnectionError):
            await service.set_dlna_preset("D", 1, SERVER, "secret-object", dlna)
    repo.set_preset.assert_not_awaited()
    assert "secret-object" not in caplog.text and "http://nas" not in caplog.text


def test_dlna_playback_is_null_for_radio():
    radio = Preset("D", 1, "u", "n", "http://x/y", source="LOCAL_INTERNET_RADIO")
    assert radio.to_dict()["dlna_playback"] is None
    v1 = Preset("D", 1, "u", "n", f"dlna://{SERVER}/o", source="DLNA")
    assert v1.to_dict()["dlna_playback"] == "reference"


# --- payload ----------------------------------------------------------------


def test_native_payload_has_no_orion_url_and_escapes():
    xml = BoseDeviceClientAdapter._build_preset_payload(
        4,
        "dlna://x/y",
        'Al"bum & <Co>',
        "http://oct:7777",
        "http://nas/c.jpg?a=1&b=2",
        "dlna-1",
        native_item=NativeContentItem(ACCOUNT, "a&b<c>", "dir"),
    )
    assert 'source="STORED_MUSIC"' in xml and 'type="dir"' in xml
    assert f'sourceAccount="{ACCOUNT}"' in xml
    assert 'location="a&amp;b&lt;c&gt;"' in xml
    assert '<itemName>Al"bum &amp; &lt;Co&gt;</itemName>' in xml
    assert "<containerArt>http://nas/c.jpg?a=1&amp;b=2</containerArt>" in xml
    assert "orion" not in xml and "LOCAL_INTERNET_RADIO" not in xml
    assert xml.startswith('<preset id="4"')


def test_native_payload_without_art_has_no_container_art():
    xml = BoseDeviceClientAdapter._build_preset_payload(
        1,
        "u",
        "n",
        "http://oct",
        "",
        "x",
        native_item=NativeContentItem(ACCOUNT, "o", "dir"),
    )
    assert "containerArt" not in xml


# --- suffix helpers ---------------------------------------------------------


def test_suffix_helpers_add_and_strip_the_track_suffix():
    assert native_location("o", "track") == "o TRACK"
    assert native_location("o", "dir") == "o"
    assert strip_native_location("o TRACK", "track") == "o"
    assert strip_native_location("o TRACK", "dir") == "o TRACK"
    assert strip_native_location("o", "track") == "o"


def test_parser_strips_the_suffix_on_read():
    xml = (
        '<presets><preset id="1"><ContentItem source="STORED_MUSIC" type="track" '
        f'location="obj-1 TRACK" sourceAccount="{ACCOUNT}"><itemName>T</itemName>'
        "</ContentItem></preset></presets>"
    ).encode()
    (preset,) = DevicePresetParser().parse_presets("D", xml)
    assert preset.station_url == f"dlna://{SERVER}/obj-1"
    assert preset.native_type == "track"


def test_marge_xml_adds_the_suffix_for_a_native_track():
    from datetime import UTC, datetime

    from opencloudtouch.marge.source_repository import MediaServerSource
    from opencloudtouch.marge.xml_builder import build_preset_response_xml

    now = datetime.now(UTC)
    row = MediaServerSource(20000001, "D", SERVER, "Server", now, now)
    track = Preset(
        "D",
        2,
        "dlna-x",
        "T",
        f"dlna://{SERVER}/obj-1",
        source="DLNA",
        native_type="track",
    )

    entry = build_preset_response_xml(track, [row])
    assert entry.findtext("location") == "obj-1 TRACK"
    assert entry.findtext("contentItemType") == "track"


async def test_marge_store_strips_the_suffix_on_read():
    from datetime import UTC, datetime

    from opencloudtouch.marge.service import MargeService
    from opencloudtouch.marge.source_repository import MediaServerSource

    now = datetime.now(UTC)
    row = MediaServerSource(20000001, "D", SERVER, "Server", now, now)
    sources = AsyncMock()
    sources.get_by_id = AsyncMock(return_value=row)
    presets = AsyncMock()
    presets.get_preset = AsyncMock(return_value=None)
    presets.set_preset = AsyncMock(side_effect=lambda p: p)
    devices = AsyncMock()
    devices.get_by_account_uuid = AsyncMock(return_value=None)
    devices.get_by_device_id = AsyncMock(return_value=MagicMock(device_id="D"))
    marge = MargeService(presets, AsyncMock(), devices, sources)

    saved = await marge.store_preset(
        "D", 2, "20000001", "T", "obj-1 TRACK", "track", "D"
    )
    assert saved.station_url == f"dlna://{SERVER}/obj-1"
    assert saved.native_type == "track"
