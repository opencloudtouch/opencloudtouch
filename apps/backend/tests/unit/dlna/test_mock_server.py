"""Tests for the deterministic mock DLNA server."""

import pytest

from opencloudtouch.devices.mock_client import MockDeviceClient
from opencloudtouch.dlna.client import DlnaBrowseError, DlnaClient
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.mock import MOCK_SERVER, mock_browse, mock_object
from opencloudtouch.dlna.models import is_audio_item


def test_mock_tree_shape():
    root = mock_browse("0", 0, 50).items
    assert [i.id for i in root] == ["albums", "photos", "single"]
    albums = mock_browse("albums", 0, 50).items
    assert len(albums) == 2
    assert all(a.media_class.endswith("musicAlbum") for a in albums)
    assert all(len(mock_browse(a.id, 0, 50).items) == 3 for a in albums)
    assert not is_audio_item(mock_browse("photos", 0, 1).items[0])
    assert mock_browse("albums", 1, 1).items[0].id == "album-2"
    assert mock_browse("albums", 1, 1).total_matches == 2
    assert mock_browse("single", 0, 50).items == []
    with pytest.raises(KeyError):
        mock_object("nope")


@pytest.mark.asyncio
async def test_discover_returns_mock_in_mock_mode(monkeypatch):
    monkeypatch.setenv("OCT_MOCK_MODE", "true")
    assert await DlnaDiscovery().discover() == [MOCK_SERVER]


@pytest.mark.asyncio
async def test_client_serves_mock_urls():
    client = DlnaClient()
    page = await client.browse(MOCK_SERVER, "album-1")
    assert [i.id for i in page.items] == ["a1-t1", "a1-t2", "a1-t3"]
    assert (await client.get_object(MOCK_SERVER, "album-1")).title == "Album One"
    with pytest.raises(DlnaBrowseError) as exc:
        await client.browse(MOCK_SERVER, "nope")
    assert exc.value.error_code == "701"


@pytest.mark.asyncio
async def test_mock_browse_stored_music_matches_dlna_ids():
    mock = MockDeviceClient(device_id="AABBCC112233", ip_address="192.0.2.1")
    account = f"{MOCK_SERVER.id}/0"
    root = await mock.browse_stored_music(account)
    assert root.error_code is None
    assert [(i.location, i.is_directory) for i in root.items] == [
        ("albums", True),
        ("photos", True),
        ("single TRACK", False),
    ]
    assert all(i.source_account == account for i in root.items)
    tracks = await mock.browse_stored_music(account, "album-1")
    assert [i.location for i in tracks.items] == [
        "a1-t1 TRACK",
        "a1-t2 TRACK",
        "a1-t3 TRACK",
    ]
    assert (await mock.browse_stored_music(account, "nope")).items == []
