"""Tests for DlnaService.get_object_path (breadcrumb of a saved object)."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.client import (
    DlnaBrowseError,
    DlnaEmptyMetadataError,
    DlnaTimeoutError,
)
from opencloudtouch.dlna.models import DlnaItem, DlnaServer
from opencloudtouch.dlna.service import DlnaService

SERVER = DlnaServer("s1", "NAS", "http://192.0.2.10/d.xml", "http://192.0.2.10/c")


def _item(oid: str, parent: str, container: bool = True) -> DlnaItem:
    return DlnaItem(id=oid, parent_id=parent, title=f"T-{oid}", is_container=container)


class FakeClient:
    def __init__(self, items: list[DlnaItem], delay: float = 0.0):
        self.by_id = {i.id: i for i in items}
        self.delay = delay
        self.calls = 0

    async def get_object(self, server, object_id):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if object_id not in self.by_id:
            raise DlnaBrowseError("No Such Object", error_code="701")
        return self.by_id[object_id]


def _service(client, timeout: float = 15.0) -> DlnaService:
    discovery = AsyncMock()
    discovery.discover.return_value = [SERVER]
    return DlnaService(discovery=discovery, client=client, timeout=timeout)


def _chain(levels: int) -> list[DlnaItem]:
    """Object ``o`` below ``levels`` ancestors ``a1`` (top) .. ``a<levels>``."""
    items = [
        _item(f"a{n}", "0" if n == 1 else f"a{n - 1}") for n in range(1, levels + 1)
    ]
    return items + [_item("o", f"a{levels}" if levels else "0", container=False)]


@pytest.mark.asyncio
async def test_three_levels_in_order_from_the_top():
    result = await _service(FakeClient(_chain(3))).get_object_path("s1", "o")
    assert result.server_name == "NAS"
    assert result.item.id == "o" and not result.item.is_container
    assert [a.id for a in result.ancestors] == ["a1", "a2", "a3"]


@pytest.mark.asyncio
async def test_object_below_root_has_no_ancestors():
    result = await _service(FakeClient(_chain(0))).get_object_path("s1", "o")
    assert result.ancestors == []


@pytest.mark.asyncio
async def test_root_object_answers_with_the_server_name():
    client = FakeClient([])
    result = await _service(client).get_object_path("s1", "0")
    assert (result.item.title, result.ancestors, client.calls) == ("NAS", [], 0)


@pytest.mark.asyncio
async def test_upnp_root_marker_ends_the_walk():
    client = FakeClient([_item("o", "-1")])
    assert (await _service(client).get_object_path("s1", "o")).ancestors == []


@pytest.mark.asyncio
async def test_sixteen_levels_are_allowed():
    result = await _service(FakeClient(_chain(16))).get_object_path("s1", "o")
    assert len(result.ancestors) == 16


@pytest.mark.asyncio
async def test_seventeen_levels_fail_with_a_bounded_number_of_calls():
    client = FakeClient(_chain(40))
    with pytest.raises(DlnaBrowseError) as exc:
        await _service(client).get_object_path("s1", "o")
    assert exc.value.error_code is None
    assert client.calls <= 17


@pytest.mark.asyncio
async def test_parent_loop_fails_without_endless_walk():
    client = FakeClient([_item("o", "a"), _item("a", "b"), _item("b", "a")])
    with pytest.raises(DlnaBrowseError) as exc:
        await _service(client).get_object_path("s1", "o")
    assert exc.value.error_code is None
    assert client.calls == 3


@pytest.mark.asyncio
async def test_object_pointing_to_itself_fails():
    client = FakeClient([_item("o", "o")])
    with pytest.raises(DlnaBrowseError):
        await _service(client).get_object_path("s1", "o")


@pytest.mark.asyncio
async def test_empty_parent_id_mid_chain_fails():
    client = FakeClient([_item("o", "a"), _item("a", "")])
    with pytest.raises(DlnaBrowseError) as exc:
        await _service(client).get_object_path("s1", "o")
    assert exc.value.error_code is None


@pytest.mark.asyncio
async def test_unknown_object_keeps_error_code_701():
    with pytest.raises(DlnaBrowseError) as exc:
        await _service(FakeClient([])).get_object_path("s1", "nope")
    assert exc.value.error_code == "701"


@pytest.mark.asyncio
async def test_missing_ancestor_keeps_error_code_701():
    with pytest.raises(DlnaBrowseError) as exc:
        await _service(FakeClient([_item("o", "gone")])).get_object_path("s1", "o")
    assert exc.value.error_code == "701"


@pytest.mark.asyncio
async def test_unknown_server_raises_lookup_error():
    with pytest.raises(LookupError):
        await _service(FakeClient([])).get_object_path("other", "o")


@pytest.mark.asyncio
async def test_one_deadline_covers_all_hops():
    # every hop (0.03 s) is far below the 0.1 s deadline, the walk of 5 hops is not
    client = FakeClient(_chain(4), delay=0.03)
    with pytest.raises(DlnaTimeoutError):
        await _service(client, timeout=0.1).get_object_path("s1", "o")


@pytest.mark.asyncio
async def test_empty_metadata_answer_means_object_not_found():
    client = AsyncMock()
    client.get_object.side_effect = DlnaEmptyMetadataError("empty")
    with pytest.raises(DlnaBrowseError) as exc:
        await _service(client).get_object_path("s1", "o")
    assert exc.value.error_code == "701"
