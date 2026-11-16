"""Tests for the deterministic fake DLNA server."""

import pytest

from opencloudtouch.dlna.client import DlnaBrowseError
from opencloudtouch.dlna.mock import (
    MOCK_SERVER,
    MOCK_UUID_SERVER,
    MockDlnaClient,
    MockDlnaDiscovery,
)
from opencloudtouch.dlna.models import is_audio_item
from opencloudtouch.dlna.service import DlnaService


@pytest.mark.asyncio
async def test_discovery_finds_the_mock_server():
    assert await MockDlnaDiscovery().discover() == [MOCK_SERVER, MOCK_UUID_SERVER]


@pytest.mark.asyncio
async def test_music_folder_has_120_tracks_in_pages():
    client = MockDlnaClient()
    first = await client.browse(MOCK_SERVER, "music", 0, 50)
    last = await client.browse(MOCK_SERVER, "music", 100, 50)

    assert (first.number_returned, first.total_matches) == (50, 120)
    assert (last.number_returned, last.total_matches) == (20, 120)
    assert first.items[0].title == "Track 001"


@pytest.mark.asyncio
async def test_albums_are_nested_three_levels_deep():
    client = MockDlnaClient()
    object_id = "albums"
    for _ in range(3):
        page = await client.browse(MOCK_SERVER, object_id)
        assert [i.is_container for i in page.items] == [True]
        object_id = page.items[0].id
    leaves = await client.browse(MOCK_SERVER, object_id)
    assert not any(i.is_container for i in leaves.items)


@pytest.mark.asyncio
async def test_mixed_folder_has_non_audio_item_and_file_cover():
    service = DlnaService(MockDlnaDiscovery(), MockDlnaClient())
    raw = await MockDlnaClient().browse(MOCK_SERVER, "mixed")
    page = await service.browse(MOCK_SERVER.id, "mixed")

    assert any(not is_audio_item(i) for i in raw.items)
    assert page.number_returned == 3
    assert [i.id for i in page.items] == ["mixed-http", "mixed-file"]
    assert [i.album_art_url for i in page.items] == [
        "http://mock-media.invalid/cover.jpg",
        None,
    ]


@pytest.mark.asyncio
async def test_first_sixty_entries_of_one_folder_are_subfolders():
    page = await MockDlnaClient().browse(MOCK_SERVER, "subfolders", 0, 200)
    assert all(i.is_container for i in page.items[:60])
    assert not any(i.is_container for i in page.items[60:])


@pytest.mark.asyncio
async def test_metadata_and_unknown_ids():
    client = MockDlnaClient()
    assert (await client.get_object(MOCK_SERVER, "music-001")).title == "Track 001"
    assert (await client.get_object(MOCK_SERVER, "0")).is_container
    for call in (
        client.get_object(MOCK_SERVER, "nope"),
        client.browse(MOCK_SERVER, "nope"),
    ):
        with pytest.raises(DlnaBrowseError) as exc:
            await call
        assert exc.value.error_code == "701"


@pytest.mark.asyncio
async def test_empty_folder_browses_to_nothing():
    page = await MockDlnaClient().browse(MOCK_SERVER, "sub-01")
    assert (page.items, page.number_returned, page.total_matches) == ([], 0, 0)
