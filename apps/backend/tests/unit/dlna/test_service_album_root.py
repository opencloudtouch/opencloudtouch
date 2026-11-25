"""Tests for the DLNA album root search (album view link)."""

from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer
from opencloudtouch.dlna.service import DlnaService

SERVER = DlnaServer("s1", "NAS", "http://192.0.2.10/d.xml", "http://192.0.2.10/c")
ALBUM = "object.container.album.musicAlbum"


def _item(item_id, parent_id, media_class=None):
    return DlnaItem(item_id, parent_id, f"t{item_id}", True, media_class=media_class)


def _service(tree):
    discovery = AsyncMock()
    discovery.discover.return_value = [SERVER]
    client = AsyncMock()
    client.browse.side_effect = lambda _s, oid, *_: BrowsePage(
        tree.get(oid, []), len(tree.get(oid, [])), None
    )
    return DlnaService(discovery=discovery, client=client)


@pytest.mark.asyncio
async def test_album_root_found_breadth_first():
    tree = {
        "0": [_item("a", "0"), _item("b", "0")],
        "a": [_item("a1", "a")],
        "a1": [_item("deep", "a1", ALBUM)],
        "b": [_item("b1", "b", ALBUM)],
    }
    assert await _service(tree).find_album_root("s1") == "b"


@pytest.mark.asyncio
async def test_album_root_none_when_no_albums():
    tree = {"0": [_item("a", "0")], "a": [_item("a1", "a")]}
    assert await _service(tree).find_album_root("s1") is None


@pytest.mark.asyncio
async def test_album_root_call_budget():
    class Tree(dict):  # endless wide tree: every container holds 5 more
        def get(self, oid, default=None):
            return [_item(f"{oid}.{i}", oid) for i in range(5)]

    service = _service(Tree())
    assert await service.find_album_root("s1") is None
    assert service.client.browse.await_count == 20


@pytest.mark.asyncio
async def test_album_root_depth_limit():
    # The album sits below depth 3, so it is not reached.
    tree = {
        "0": [_item("1", "0")],
        "1": [_item("2", "1")],
        "2": [_item("3", "2")],
        "3": [_item("4", "3")],
        "4": [_item("x", "4", ALBUM)],
    }
    service = _service(tree)
    assert await service.find_album_root("s1") is None
    assert service.client.browse.await_count == 4
