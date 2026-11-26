"""Tests for the live availability state of registered media servers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import (
    CodedApiError,
    DeviceConnectionError,
    DeviceNotFoundError,
)
from opencloudtouch.devices.client import SpeakerSource, StoredMusicBrowse
from opencloudtouch.devices.repository import Device
from opencloudtouch.dlna.native_service import (
    DlnaNativeService,
    NativeState,
    _fetch_presets,
)
from opencloudtouch.marge.source_repository import MediaServerSource
from opencloudtouch.presets.models import Preset

ACCOUNT = "00000000-0000-4000-8000-000000000001"
UDN = "Aa000000-0000-4000-8000-0000000000Bb"


def _device(account: str | None = ACCOUNT) -> Device:
    return Device(
        device_id="device-a",
        ip="192.0.2.10",
        name="Speaker",
        model="SoundTouch 10",
        mac_address="000000000000",
        firmware_version="27.0.6",
        marge_account_uuid=account,
    )


def _row(server_id: str = UDN) -> MediaServerSource:
    now = datetime.now(UTC)
    return MediaServerSource(20000000, ACCOUNT, server_id, "NAS", now, now)


def _source(account: str = f"{UDN}/0", status: str = "READY") -> SpeakerSource:
    return SpeakerSource("STORED_MUSIC", account, status, "NAS")


def _client(sources=(), listed=(UDN,), browse_error=None) -> AsyncMock:
    client = AsyncMock()
    client.get_source_list.return_value = list(sources)
    client.list_media_servers.return_value = list(listed)
    client.browse_stored_music.return_value = StoredMusicBrowse([], browse_error)
    return client


def _service(client, rows=(), device=None) -> tuple[DlnaNativeService, AsyncMock]:
    device = device or _device()
    source_repo = AsyncMock()
    source_repo.list_for_account.return_value = list(rows)
    device_repo = AsyncMock()
    device_repo.get_by_device_id.side_effect = lambda device_id: (
        device if device_id == device.device_id else None
    )
    service = DlnaNativeService(
        source_repo, device_repo, client_factory=lambda d: client
    )
    return service, source_repo


async def test_not_enabled_without_row_or_source():
    client = _client(sources=[SpeakerSource("AUX", "AUX", "READY", "AUX")])
    service, _ = _service(client)
    assert await service.read_state("device-a", UDN) is NativeState.NOT_ENABLED
    assert await service.read_states("device-a") == {}
    client.browse_stored_music.assert_not_called()
    client.close.assert_awaited()


async def test_unavailable_when_source_not_ready():
    service, _ = _service(_client(sources=[_source(status="UNAVAILABLE")]))
    assert await service.read_state("device-a", UDN) is NativeState.UNAVAILABLE


async def test_row_without_source_is_unavailable():
    service, _ = _service(_client(), rows=[_row()])
    assert await service.read_state("device-a", UDN) is NativeState.UNAVAILABLE


async def test_unavailable_when_not_listed_by_speaker():
    client = _client(sources=[_source()], listed=["other-udn"])
    service, _ = _service(client, rows=[_row()])
    assert await service.read_state("device-a", UDN) is NativeState.UNAVAILABLE
    client.browse_stored_music.assert_not_called()


async def test_ready_when_listed_and_browsable():
    client = _client(sources=[_source()])
    service, source_repo = _service(client, rows=[_row()])
    assert await service.read_state("device-a", UDN) is NativeState.READY
    client.browse_stored_music.assert_awaited_once_with(f"{UDN}/0")
    source_repo.list_for_account.assert_awaited_once_with(ACCOUNT)


async def test_browse_error_is_unavailable():
    service, _ = _service(_client(sources=[_source()], browse_error=1608))
    assert await service.read_state("device-a", UDN) is NativeState.UNAVAILABLE


async def test_browse_connection_error_is_unavailable():
    client = _client(sources=[_source()])
    client.browse_stored_music.side_effect = DeviceConnectionError("192.0.2.10", "x")
    service, _ = _service(client)
    assert await service.read_state("device-a", UDN) is NativeState.UNAVAILABLE


async def test_list_call_failure_falls_back_to_browse():
    client = _client(sources=[_source()])
    client.list_media_servers.side_effect = DeviceConnectionError("192.0.2.10", "x")
    service, _ = _service(client)
    assert await service.read_state("device-a", UDN) is NativeState.READY
    client.browse_stored_music.assert_awaited_once()


async def test_sources_failure_is_unavailable_for_rows_only():
    client = _client()
    client.get_source_list.side_effect = DeviceConnectionError("192.0.2.10", "x")
    service, _ = _service(client, rows=[_row()])
    assert await service.read_states("device-a") == {UDN: NativeState.UNAVAILABLE}
    assert await service.read_state("device-a", "other") is NativeState.NOT_ENABLED


async def test_no_state_is_cached_between_calls():
    client = _client(sources=[_source()])
    service, _ = _service(client, rows=[_row()])
    await service.read_state("device-a", UDN)
    await service.read_state("device-a", UDN)
    assert client.get_source_list.await_count == 2
    assert client.list_media_servers.await_count == 2
    assert client.browse_stored_music.await_count == 2


async def test_udn_compare_is_case_insensitive():
    client = _client(sources=[_source()], listed=[UDN.upper()])
    service, _ = _service(client, rows=[_row(UDN.lower())])
    assert await service.read_state("device-a", UDN.lower()) is NativeState.READY


async def test_speaker_spelling_of_udn_is_returned():
    client = _client(sources=[_source()])
    service, _ = _service(client, rows=[_row(UDN.lower())])
    assert await service.read_states("device-a") == {UDN: NativeState.READY}
    client.browse_stored_music.assert_awaited_once_with(f"{UDN}/0")


async def test_empty_account_stored_music_entries_are_ignored():
    client = _client(sources=[_source(account="", status="UNAVAILABLE")])
    service, _ = _service(client)
    assert await service.read_states("device-a") == {}


async def test_device_without_account_uses_sources_only():
    client = _client(sources=[_source()])
    service, source_repo = _service(client, device=_device(account=None))
    assert await service.read_states("device-a") == {UDN: NativeState.READY}
    source_repo.list_for_account.assert_not_called()


async def test_unknown_device_raises():
    service, _ = _service(_client())
    with pytest.raises(DeviceNotFoundError):
        await service.read_states("missing")


# --- enable / remove (task 10) ---

PRESETS_XML = f"""<presets>
  <preset id="1"><ContentItem source="TUNEIN" location="/v1/playback/station/s1"
    sourceAccount=""><itemName>Radio</itemName></ContentItem></preset>
  <preset id="3"><ContentItem source="STORED_MUSIC" location="7$1"
    sourceAccount="{UDN.lower()}/0"><itemName>Album</itemName></ContentItem></preset>
  <preset id="5"><ContentItem source="STORED_MUSIC" location="9"
    sourceAccount="other-udn/0"><itemName>Other</itemName></ContentItem></preset>
</presets>""".encode()


def _native(client, rows=(), migration_error=None, presets=PRESETS_XML):
    source_repo = AsyncMock()
    source_repo.list_for_account.return_value = list(rows)
    device_repo = AsyncMock()
    device_repo.get_by_device_id.return_value = _device()
    migrations = AsyncMock()
    migrations.status.return_value = (0, migration_error)
    presets_xml = AsyncMock(return_value=presets)
    sleep = AsyncMock()
    service = DlnaNativeService(
        source_repo,
        device_repo,
        client_factory=lambda d: client,
        sleep=sleep,
        poll_interval=1.0,
        ready_timeout=3.0,
        migration_service=migrations,
        presets_xml=presets_xml,
    )
    return service, source_repo, presets_xml, sleep


async def test_enable_refused_when_migration_failed():
    client = _client()
    service, *_ = _native(client, migration_error="RuntimeError: boom")
    with pytest.raises(CodedApiError) as exc:
        await service.enable("device-a", UDN, "NAS")
    assert exc.value.status_code == 409
    assert exc.value.code == error_codes.DLNA_MIGRATION_FAILED
    assert exc.value.extra == {"reason": "RuntimeError: boom"}
    client.register_media_server.assert_not_called()


async def test_enable_skips_write_when_ready():
    client = _client(sources=[_source()])
    service, *_ = _native(client, rows=[_row()])
    assert await service.enable("device-a", UDN, "NAS") is NativeState.READY
    client.register_media_server.assert_not_called()


async def test_enable_uses_speaker_udn_spelling():
    client = _client(listed=[UDN])
    service, *_ = _native(client)
    await service.enable("device-a", UDN.lower(), "NAS")
    client.register_media_server.assert_awaited_once_with(UDN, "NAS")


async def test_enable_waits_for_listing():
    client = _client()
    client.list_media_servers.side_effect = [[UDN], [], [], [UDN], [UDN]]
    client.get_source_list.side_effect = [[], [_source()]]
    service, _, _, sleep = _native(client)
    assert await service.enable("device-a", UDN, "NAS") is NativeState.READY
    assert sleep.await_count == 2
    client.register_media_server.assert_awaited_once()


async def test_enable_not_listed_returns_unavailable_no_reregister():
    client = _client(listed=[])
    service, _, _, sleep = _native(client, rows=[_row()])
    assert await service.enable("device-a", UDN, "NAS") is NativeState.UNAVAILABLE
    client.register_media_server.assert_awaited_once_with(UDN, "NAS")
    assert sleep.await_count == 3


async def test_remove_with_slots_409_lists_live_slots():
    client = _client(sources=[_source()])
    service, *_ = _native(client)
    with pytest.raises(CodedApiError) as exc:
        await service.remove("device-a", UDN)
    assert exc.value.status_code == 409
    assert exc.value.code == error_codes.DLNA_NATIVE_SLOTS_AFFECTED
    assert exc.value.extra == {"slots": [3]}
    client.remove_media_server.assert_not_called()


async def test_remove_force_removes_and_keeps_presets():
    client = _client(sources=[_source()])
    service, source_repo, *_ = _native(client, rows=[_row(UDN.lower())])
    await service.remove("device-a", UDN.lower(), force=True)
    client.remove_media_server.assert_awaited_once_with(UDN)
    client.store_preset.assert_not_called()
    client.remove_preset.assert_not_called()
    source_repo.delete.assert_awaited_once_with(ACCOUNT, 20000000)


async def test_remove_without_slots():
    client = _client(sources=[_source(account="other-udn/0")])
    service, source_repo, *_ = _native(client, presets=b"<presets/>")
    await service.remove("device-a", UDN)
    client.remove_media_server.assert_awaited_once_with(UDN)
    source_repo.delete.assert_not_called()  # callback already removed the row


async def test_affected_slots_reads_live_presets():
    service, _, presets_xml, _ = _native(_client())
    assert await service.affected_slots("device-a", UDN) == [3]
    assert await service.affected_slots("device-a", UDN) == [3]
    presets_xml.assert_awaited_with("192.0.2.10")
    assert presets_xml.await_count == 2


def _preset(slot: int, source: str, account: str | None) -> Preset:
    return Preset(
        "device-a", slot, "uuid", "Item", "loc", source=source, source_account=account
    )


async def test_affected_slots_mock_mode_reads_oct_rows():
    """Mock speakers keep no /presets: the device's OCT preset rows are used."""
    presets_xml = AsyncMock()
    preset_repo = AsyncMock()
    preset_repo.get_all_presets.return_value = [
        _preset(2, "TUNEIN", None),
        _preset(4, "STORED_MUSIC", f"{UDN.lower()}/0"),
        _preset(6, "STORED_MUSIC", "other-udn/0"),
    ]
    device_repo = AsyncMock()
    device_repo.get_by_device_id.return_value = _device()
    service = DlnaNativeService(
        AsyncMock(), device_repo, presets_xml=presets_xml, preset_repo=preset_repo
    )
    assert await service.affected_slots("device-a", UDN) == [4]
    preset_repo.get_all_presets.assert_awaited_with("device-a")
    presets_xml.assert_not_called()


async def test_enable_poll_tolerates_list_failure():
    client = _client()
    client.list_media_servers.side_effect = [
        [UDN],
        DeviceConnectionError("192.0.2.10", "x"),
        [UDN],
        [UDN],
    ]
    service, _, _, sleep = _native(client)
    await service.enable("device-a", UDN, "NAS")
    assert sleep.await_count == 1


@respx.mock
async def test_fetch_presets_reads_speaker_and_maps_errors():
    route = respx.get("http://192.0.2.10:8090/presets")
    route.return_value = httpx.Response(200, content=b"<presets/>")
    assert await _fetch_presets("192.0.2.10") == b"<presets/>"
    route.return_value = httpx.Response(500)
    with pytest.raises(DeviceConnectionError):
        await _fetch_presets("192.0.2.10")
