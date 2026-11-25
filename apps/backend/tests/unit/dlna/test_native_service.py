"""Tests for the live availability state of registered media servers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.devices.client import SpeakerSource, StoredMusicBrowse
from opencloudtouch.devices.repository import Device
from opencloudtouch.dlna.native_service import DlnaNativeService, NativeState
from opencloudtouch.marge.source_repository import MediaServerSource

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
