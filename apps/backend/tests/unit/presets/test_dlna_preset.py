"""Tests for PresetService.set_dlna_preset: speaker first, then DB."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.core.exceptions import (
    CodedApiError,
    DeviceConnectionError,
    DeviceNotFoundError,
)
from opencloudtouch.devices.client import StoredMusicBrowse, StoredMusicItem
from opencloudtouch.dlna.models import DlnaItem, DlnaServer, ObjectPath
from opencloudtouch.presets.service import PresetService

SERVER = "uuid:abc"


def _item(location="42", is_directory=True, name="Album") -> StoredMusicItem:
    return StoredMusicItem(
        name=name,
        is_directory=is_directory,
        source="STORED_MUSIC",
        location=location,
        source_account=f"{SERVER}/0",
        item_name=name,
    )


@pytest.fixture
def repo():
    r = AsyncMock()
    r.set_preset = AsyncMock(side_effect=lambda p: p)
    return r


@pytest.fixture
def device_repo():
    r = AsyncMock()
    device = MagicMock()
    device.ip = "192.0.2.10"
    r.get_by_device_id = AsyncMock(return_value=device)
    return r


@pytest.fixture
def speaker():
    c = AsyncMock()
    c.browse_stored_music = AsyncMock(return_value=StoredMusicBrowse([_item()]))
    c.store_native_preset = AsyncMock()
    with patch("opencloudtouch.devices.adapter.get_device_client", return_value=c):
        yield c


@pytest.fixture
def dlna():
    d = MagicMock()
    d.first_child_is_audio = AsyncMock(return_value=True)
    server = DlnaServer(SERVER, "NAS", "http://nas:1/d.xml", "http://nas:1/ctl")
    d.resolve = AsyncMock(return_value=server)
    art = DlnaItem("42", "0", "Album", True, album_art_url="http://nas:1/art.jpg")
    d.get_object_path = AsyncMock(return_value=ObjectPath("NAS", art, []))
    return d


@pytest.fixture
def service(repo, device_repo, dlna):
    return PresetService(repo, device_repo, dlna_service=dlna)


async def _save(service, **kw):
    args = dict(
        device_id="D1", preset_number=2, server_id=SERVER, parent_id="0", object_id="42"
    )
    args.update(kw)
    return await service.set_dlna_preset(**args)


@pytest.mark.asyncio
async def test_saves_folder_native_speaker_first_then_db(service, speaker, repo, dlna):
    order = []
    speaker.store_native_preset.side_effect = lambda *a, **k: order.append("speaker")
    repo.set_preset.side_effect = lambda p: order.append("db") or p

    preset = await _save(service)

    assert order == ["speaker", "db"]
    speaker.browse_stored_music.assert_awaited_once_with(f"{SERVER}/0", None, 1, 50)
    speaker.store_native_preset.assert_awaited_once()
    assert speaker.store_native_preset.await_args.args[2] == "http://nas:1/art.jpg"
    assert preset.station_uuid == "STORED_MUSIC_2"
    assert preset.source == "STORED_MUSIC"
    assert preset.station_favicon == "http://nas:1/art.jpg"
    assert preset.is_dlna


@pytest.mark.asyncio
async def test_speaker_failure_leaves_db_unchanged(service, speaker, repo):
    speaker.store_native_preset.side_effect = DeviceConnectionError("x", "down")
    with pytest.raises(DeviceConnectionError):
        await _save(service)
    repo.set_preset.assert_not_awaited()


@pytest.mark.asyncio
async def test_track_location_has_track_suffix_and_account(service, speaker):
    speaker.browse_stored_music.return_value = StoredMusicBrowse(
        [_item("42 TRACK", is_directory=False, name="Song")]
    )
    preset = await _save(service, parent_id="7")
    speaker.browse_stored_music.assert_awaited_once_with(f"{SERVER}/0", "7", 1, 50)
    assert preset.station_url == "42 TRACK"
    assert preset.source_account == f"{SERVER}/0"
    assert preset.station_name == "Song"


@pytest.mark.asyncio
async def test_folder_without_audio_first_409_and_no_write(
    service, speaker, repo, dlna
):
    dlna.first_child_is_audio.return_value = False
    with pytest.raises(CodedApiError) as exc:
        await _save(service)
    assert exc.value.status_code == 409
    assert exc.value.code == "dlna_folder_no_audio_first"
    assert exc.value.extra == {"title": "Album"}
    speaker.store_native_preset.assert_not_awaited()
    repo.set_preset.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_flag_saves_anyway(service, speaker, dlna):
    dlna.first_child_is_audio.return_value = False
    await _save(service, confirm=True)
    speaker.store_native_preset.assert_awaited_once()


@pytest.mark.asyncio
async def test_object_not_found_404(service, speaker, repo):
    with pytest.raises(CodedApiError) as exc:
        await _save(service, object_id="999")
    assert exc.value.status_code == 404
    assert exc.value.code == "dlna_object_not_found"
    repo.set_preset.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_speaker_error_is_502(service, speaker):
    speaker.browse_stored_music.return_value = StoredMusicBrowse([], error_code=1005)
    with pytest.raises(CodedApiError) as exc:
        await _save(service)
    assert (exc.value.status_code, exc.value.code) == (502, "dlna_upstream_error")
    # 1602 is retried inside the client; the service browses exactly once.
    speaker.browse_stored_music.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_device_404(service, device_repo):
    device_repo.get_by_device_id.return_value = None
    with pytest.raises(DeviceNotFoundError):
        await _save(service)


@pytest.mark.asyncio
async def test_other_slots_untouched(service, speaker, repo):
    await _save(service, preset_number=4)
    repo.set_preset.assert_awaited_once()
    assert speaker.store_native_preset.await_args.args[0] == 4
    repo.clear_preset.assert_not_called()
    speaker.remove_preset.assert_not_called()


@pytest.mark.asyncio
async def test_foreign_artwork_host_is_dropped(service, speaker, dlna):
    art = DlnaItem("42", "0", "Album", True, album_art_url="http://evil:1/a.jpg")
    dlna.get_object_path.return_value = ObjectPath("NAS", art, [])
    preset = await _save(service)
    assert preset.station_favicon is None


@pytest.mark.asyncio
async def test_speaker_unreachable_on_browse_propagates(service, speaker, repo):
    speaker.browse_stored_music.side_effect = DeviceConnectionError("x", "down")
    with pytest.raises(DeviceConnectionError):
        await _save(service)
    repo.set_preset.assert_not_awaited()
    speaker.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_first_child_check_server_missing_maps_to_coded_error(
    service, speaker, dlna
):
    dlna.first_child_is_audio.side_effect = LookupError("gone")
    with pytest.raises(CodedApiError) as exc:
        await _save(service)
    assert (exc.value.status_code, exc.value.code) == (404, "dlna_server_not_found")
    speaker.store_native_preset.assert_not_awaited()


@pytest.mark.asyncio
async def test_track_skips_first_child_check(service, speaker, dlna):
    speaker.browse_stored_music.return_value = StoredMusicBrowse(
        [_item("42 TRACK", is_directory=False, name="Song")]
    )
    await _save(service)
    dlna.first_child_is_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_artwork_lookup_failure_saves_without_cover(service, speaker, dlna):
    dlna.get_object_path.side_effect = LookupError("gone")
    preset = await _save(service)
    assert preset.station_favicon is None
    assert speaker.store_native_preset.await_args.args[2] == ""


def _page(start: int, count: int) -> list[StoredMusicItem]:
    return [_item(str(1000 + n)) for n in range(start, start + count)]


@pytest.mark.asyncio
async def test_large_parent_is_paged_until_the_object(service, speaker):
    """One 1000-item /navigate of a 1447-item parent timed out (T22 2a)."""
    speaker.browse_stored_music.side_effect = [
        StoredMusicBrowse(_page(0, 50), total=1447),
        StoredMusicBrowse(_page(50, 50) + [_item("42")], total=1447),
    ]
    preset = await _save(service, parent_id="32")
    assert [c.args for c in speaker.browse_stored_music.await_args_list] == [
        (f"{SERVER}/0", "32", 1, 50),
        (f"{SERVER}/0", "32", 51, 50),
    ]
    assert preset.station_url == "42"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "browse",
    [StoredMusicBrowse(_page(0, 50), total=50), StoredMusicBrowse(_page(0, 3))],
    ids=["total-reached", "short-page"],
)
async def test_paging_stops_at_the_end_with_404(service, speaker, browse):
    speaker.browse_stored_music.return_value = browse
    with pytest.raises(CodedApiError) as exc:
        await _save(service, object_id="999")
    assert exc.value.code == "dlna_object_not_found"
    speaker.browse_stored_music.assert_awaited_once()


@pytest.mark.asyncio
async def test_paging_over_time_budget_is_504(service, speaker, repo):
    speaker.browse_stored_music.return_value = StoredMusicBrowse(
        _page(0, 50), total=5000
    )
    clock = iter([0.0, 10.0, 61.0])
    with patch("opencloudtouch.presets.service.time.monotonic", lambda: next(clock)):
        with pytest.raises(CodedApiError) as exc:
            await _save(service, object_id="999")
    assert (exc.value.status_code, exc.value.code) == (504, "dlna_server_timeout")
    assert speaker.browse_stored_music.await_count == 1
    repo.set_preset.assert_not_awaited()
