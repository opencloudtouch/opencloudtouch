"""Tests for the DLNA object path (edit prefill) and BrowseMetadata."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from opencloudtouch.dlna.client import DlnaBrowseError, DlnaClient
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer
from opencloudtouch.dlna.service import DlnaService

SERVER = DlnaServer("s1", "NAS", "http://192.0.2.10/d.xml", "http://192.0.2.10/c")


def _item(item_id, parent_id):
    return DlnaItem(item_id, parent_id, f"t{item_id}", True)


def _service(objects):
    discovery = AsyncMock()
    discovery.discover.return_value = [SERVER]
    client = AsyncMock()
    client.get_object.side_effect = lambda _s, oid: objects[oid]
    return DlnaService(discovery=discovery, client=client)


@pytest.mark.asyncio
async def test_path_walks_to_root():
    objs = {"3": _item("3", "2"), "2": _item("2", "1"), "1": _item("1", "0")}
    result = await _service(objs).get_object_path("s1", "3")
    assert result.server_name == "NAS"
    assert result.item.id == "3"
    assert [a.id for a in result.ancestors] == ["1", "2"]


@pytest.mark.asyncio
async def test_path_of_root_is_empty():
    service = _service({})
    result = await service.get_object_path("s1", "0")
    assert (result.item.id, result.item.is_container, result.ancestors) == (
        "0",
        True,
        [],
    )
    service.client.get_object.assert_not_called()


@pytest.mark.asyncio
async def test_path_cycle_is_error():
    objs = {"1": _item("1", "2"), "2": _item("2", "1")}
    with pytest.raises(DlnaBrowseError) as exc:
        await _service(objs).get_object_path("s1", "1")
    assert exc.value.error_code is None


@pytest.mark.asyncio
async def test_path_too_deep_is_error():
    objs = {str(i): _item(str(i), str(i + 1)) for i in range(1, 40)}
    service = _service(objs)
    with pytest.raises(DlnaBrowseError):
        await service.get_object_path("s1", "1")
    assert service.client.get_object.await_count == 17


@pytest.mark.asyncio
async def test_path_missing_object_404():
    service = _service({})
    service.client.get_object.side_effect = DlnaBrowseError("x", error_code="701")
    with pytest.raises(DlnaBrowseError) as exc:
        await service.get_object_path("s1", "9")
    assert exc.value.error_code == "701"


def _patched_http(text):
    seen = []

    def respond(request):
        seen.append(request.content.decode())
        return httpx.Response(200, text=text)

    http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    return seen, patch(
        "opencloudtouch.dlna.client.httpx.AsyncClient", return_value=http
    )


def _soap(didl_body):
    didl = (
        '&lt;DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/"&gt;'
        f"{didl_body}&lt;/DIDL-Lite&gt;"
    )
    return (
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
        '<u:BrowseResponse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">'
        f"<Result>{didl}</Result><NumberReturned>1</NumberReturned>"
        "<TotalMatches>1</TotalMatches></u:BrowseResponse></s:Body></s:Envelope>"
    )


@pytest.mark.asyncio
async def test_get_object_uses_browse_metadata():
    body = (
        '&lt;container id="f" parentID="p"&gt;'
        "&lt;dc:title&gt;F&lt;/dc:title&gt;&lt;/container&gt;"
    )
    seen, patched = _patched_http(_soap(body))
    with patched:
        item = await DlnaClient().get_object(SERVER, "f")
    assert (item.id, item.parent_id, item.title) == ("f", "p", "F")
    assert "<BrowseFlag>BrowseMetadata</BrowseFlag>" in seen[0]


@pytest.mark.asyncio
async def test_get_object_empty_answer_is_701():
    _, patched = _patched_http(_soap(""))
    with patched, pytest.raises(DlnaBrowseError) as exc:
        await DlnaClient().get_object(SERVER, "gone")
    assert exc.value.error_code == "701"


@pytest.mark.asyncio
async def test_browse_still_sends_direct_children():
    seen, patched = _patched_http(_soap(""))
    with patched:
        page = await DlnaClient().browse(SERVER, "0")
    assert page == BrowsePage([], 1, 1)
    assert "<BrowseFlag>BrowseDirectChildren</BrowseFlag>" in seen[0]
