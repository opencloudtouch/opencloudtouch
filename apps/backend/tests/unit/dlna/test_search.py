"""Tests for the DLNA library search (UPnP ContentDirectory Search)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_dlna_service
from opencloudtouch.core.exception_handlers import coded_api_error_handler
from opencloudtouch.core.exceptions import CodedApiError
from opencloudtouch.dlna import routes
from opencloudtouch.dlna.client import (
    DlnaBrowseError,
    DlnaClient,
    DlnaSearchUnsupportedError,
)
from opencloudtouch.dlna.errors import classify
from opencloudtouch.dlna.mock import MOCK_SERVER
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer
from opencloudtouch.dlna.service import DlnaService, build_search_criteria

SERVER = DlnaServer("s1", "N", "http://192.0.2.1/d", "http://192.0.2.1/c")
ALL_CAPS = ["upnp:class", "dc:title", "upnp:artist", "upnp:album"]
TITLE = 'dc:title contains "abba"'

SEARCH_RESPONSE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <u:SearchResponse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <Result>&lt;DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"&gt;
&lt;item id="t9" parentID="album-7"&gt;&lt;dc:title&gt;Waterloo&lt;/dc:title&gt;
&lt;upnp:class&gt;object.item.audioItem.musicTrack&lt;/upnp:class&gt;
&lt;res protocolInfo="http-get:*:audio/mpeg:*"&gt;http://192.0.2.1/t9.mp3&lt;/res&gt;
&lt;/item&gt;&lt;/DIDL-Lite&gt;</Result>
      <NumberReturned>1</NumberReturned>
      <TotalMatches>7</TotalMatches>
      <UpdateID>1</UpdateID>
    </u:SearchResponse>
  </s:Body>
</s:Envelope>"""

CAPS_RESPONSE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <u:GetSearchCapabilitiesResponse
        xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <SearchCaps>upnp:class, dc:title,upnp:artist,upnp:album</SearchCaps>
    </u:GetSearchCapabilitiesResponse>
  </s:Body>
</s:Envelope>"""

EMPTY_CAPS_RESPONSE = CAPS_RESPONSE.replace(
    "upnp:class, dc:title,upnp:artist,upnp:album", ""
)


def _patched(text, seen):
    def respond(request):
        seen.append(request)
        return httpx.Response(200, text=text)

    return patch(
        "opencloudtouch.dlna.client.httpx.AsyncClient",
        return_value=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )


# --- criteria builder ---


def test_criteria_all_kinds_with_full_caps():
    any_field = (
        '(dc:title contains "abba" or upnp:artist contains "abba"'
        ' or upnp:album contains "abba")'
    )
    assert build_search_criteria("abba", "all", ALL_CAPS) == any_field
    assert build_search_criteria("abba", "tracks", ALL_CAPS) == (
        any_field + ' and upnp:class derivedfrom "object.item.audioItem"'
    )
    assert build_search_criteria("abba", "folders", ALL_CAPS) == (
        any_field + ' and upnp:class derivedfrom "object.container"'
    )


def test_criteria_uses_only_listed_properties():
    assert build_search_criteria("abba", "all", ["dc:title"]) == f"({TITLE})"
    assert build_search_criteria("abba", "all", ["dc:title", "upnp:album"]) == (
        f'({TITLE} or upnp:album contains "abba")'
    )
    # Without upnp:class the kind cannot be expressed upstream.
    assert build_search_criteria("abba", "tracks", ["dc:title"]) == f"({TITLE})"
    assert build_search_criteria("abba", "all", ["*"]).count("contains") == 3


def test_criteria_escapes_backslash_and_quote():
    assert build_search_criteria('a"b\\c', "all", ["dc:title"]) == (
        '(dc:title contains "a\\"b\\\\c")'
    )


def test_criteria_without_title_is_none():
    assert build_search_criteria("abba", "all", ["upnp:artist"]) is None
    assert build_search_criteria("abba", "all", []) is None


# --- client ---


@pytest.mark.asyncio
async def test_search_sends_soap_request_and_parses_parent_id():
    seen: list[httpx.Request] = []
    with _patched(SEARCH_RESPONSE, seen):
        page = await DlnaClient().search(SERVER, "0", 'dc:title contains "a&b"', 5, 20)
    body = seen[0].content.decode()
    assert seen[0].headers["SOAPACTION"] == (
        '"urn:schemas-upnp-org:service:ContentDirectory:1#Search"'
    )
    assert "<u:Search " in body
    assert "<ContainerID>0</ContainerID>" in body
    assert (
        "<SearchCriteria>dc:title contains &quot;a&amp;b&quot;</SearchCriteria>" in body
    )
    assert "<StartingIndex>5</StartingIndex>" in body
    assert "<RequestedCount>20</RequestedCount>" in body
    assert (page.number_returned, page.total_matches) == (1, 7)
    assert page.items[0].parent_id == "album-7"
    assert page.items[0].title == "Waterloo"


@pytest.mark.asyncio
async def test_get_search_capabilities_parses_list():
    seen: list[httpx.Request] = []
    with _patched(CAPS_RESPONSE, seen):
        caps = await DlnaClient().get_search_capabilities(SERVER)
    assert caps == ALL_CAPS
    assert seen[0].headers["SOAPACTION"].endswith('#GetSearchCapabilities"')
    with _patched(EMPTY_CAPS_RESPONSE, []):
        assert await DlnaClient().get_search_capabilities(SERVER) == []


@pytest.mark.asyncio
async def test_search_rejects_non_search_response():
    with _patched(CAPS_RESPONSE, []), pytest.raises(DlnaBrowseError):
        await DlnaClient().search(SERVER, "0", TITLE, 0, 10)


# --- service ---


def _service(caps, page=None, clock=None):
    client = AsyncMock()
    client.get_search_capabilities.return_value = caps
    client.search.return_value = page or BrowsePage([], 0, 0)
    service = DlnaService(
        discovery=AsyncMock(), client=client, cache_ttl=30.0, clock=clock or (lambda: 0)
    )
    service._servers[SERVER.id] = SERVER
    service._last_seen[SERVER.id] = 0
    service._cache_expires_at = 1e9
    return service, client


@pytest.mark.asyncio
async def test_service_search_builds_criteria_and_filters():
    track = DlnaItem(
        "t1", "a", "T", False, media_class="object.item.audioItem.musicTrack"
    )
    folder = DlnaItem("f1", "0", "F", True, media_class="object.container")
    image = DlnaItem("i1", "0", "I", False, media_class="object.item.imageItem")
    service, client = _service(["dc:title"], BrowsePage([track, folder, image], 3, 3))
    page = await service.search_page("s1", "abba", "tracks", "c", 4, 10)
    client.search.assert_awaited_once_with(SERVER, "c", f"({TITLE})", 4, 10)
    # Kind applied locally when upnp:class is not searchable; images never pass.
    assert [i.id for i in page.items] == ["t1"]
    assert (page.number_returned, page.total_matches) == (3, 3)


@pytest.mark.asyncio
async def test_service_caches_capabilities_for_discovery_ttl():
    now = [0.0]
    service, client = _service(ALL_CAPS, clock=lambda: now[0])
    await service.search_page("s1", "abba", "all", "0", 0, 10)
    now[0] = 29.0
    await service.search_page("s1", "abba", "all", "0", 0, 10)
    assert client.get_search_capabilities.await_count == 1
    now[0] = 31.0
    await service.search_page("s1", "abba", "all", "0", 0, 10)
    assert client.get_search_capabilities.await_count == 2


@pytest.mark.asyncio
async def test_service_without_title_search_is_unsupported():
    service, client = _service(["upnp:artist"])
    with pytest.raises(DlnaSearchUnsupportedError):
        await service.search_page("s1", "abba", "all", "0", 0, 10)
    client.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_missing_search_action_is_unsupported():
    service, client = _service([])
    client.get_search_capabilities.side_effect = DlnaBrowseError(
        "Invalid Action", error_code="401"
    )
    with pytest.raises(DlnaSearchUnsupportedError):
        await service.search_page("s1", "abba", "all", "0", 0, 10)
    client.get_search_capabilities.side_effect = DlnaBrowseError("down")
    service._search_caps.clear()
    with pytest.raises(DlnaBrowseError) as exc:
        await service.search_page("s1", "abba", "all", "0", 0, 10)
    assert not isinstance(exc.value, DlnaSearchUnsupportedError)


def test_classify_unsupported_is_409():
    assert classify(DlnaSearchUnsupportedError("x"))[:2] == (
        409,
        "dlna_search_unsupported",
    )


# --- routes ---


def _client(service):
    app = FastAPI()
    app.include_router(routes.router)
    app.add_exception_handler(CodedApiError, coded_api_error_handler)
    app.dependency_overrides[get_dlna_service] = lambda: service
    return TestClient(app)


URL = "/api/dlna/servers/s1/search"


def test_search_route_returns_browse_page_with_parent_id():
    service = AsyncMock()
    item = DlnaItem("t9", "album-7", "Waterloo", False)
    service.search_page.return_value = BrowsePage([item], 1, 7)
    res = _client(service).get(
        URL,
        params={
            "q": "  wat ",
            "kind": "tracks",
            "container_id": "c",
            "starting_index": 2,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["items"][0]["parent_id"] == "album-7"
    assert (body["object_id"], body["next_index"], body["has_more"]) == ("c", 3, True)
    service.search_page.assert_awaited_once_with("s1", "wat", "tracks", "c", 2, 50)


@pytest.mark.parametrize(
    "params",
    [
        {"q": " a "},
        {"q": "x" * 101},
        {},
        {"q": "abba", "kind": "albums"},
        {"q": "abba", "requested_count": 51},
        {"q": "abba", "starting_index": -1},
    ],
)
def test_search_route_validation_is_422(params):
    service = AsyncMock()
    assert _client(service).get(URL, params=params).status_code == 422
    service.search_page.assert_not_awaited()


def test_search_route_unsupported_is_coded_409():
    service = AsyncMock()
    service.search_page.side_effect = DlnaSearchUnsupportedError("no search")
    res = _client(service).get(URL, params={"q": "abba"})
    assert res.status_code == 409
    assert res.json()["code"] == "dlna_search_unsupported"


def test_search_route_maps_timeout_like_browse():
    from opencloudtouch.dlna.client import DlnaTimeoutError

    service = AsyncMock()
    service.search_page.side_effect = DlnaTimeoutError("slow")
    res = _client(service).get(URL, params={"q": "abba"})
    assert (res.status_code, res.json()["code"]) == (504, "dlna_server_timeout")


# --- mock media server ---


@pytest.mark.asyncio
async def test_mock_server_search():
    client = DlnaClient()
    assert "dc:title" in await client.get_search_capabilities(MOCK_SERVER)
    service = DlnaService(discovery=AsyncMock(), client=client)
    service._servers[MOCK_SERVER.id] = MOCK_SERVER
    service._last_seen[MOCK_SERVER.id] = 0
    service._cache_expires_at = 1e12

    tracks = await service.search_page(MOCK_SERVER.id, "TWO track", "all", "0", 0, 50)
    assert [i.id for i in tracks.items] == ["a2-t1", "a2-t2", "a2-t3"]
    assert tracks.items[0].parent_id == "album-2"
    folders = await service.search_page(MOCK_SERVER.id, "album", "folders", "0", 0, 50)
    assert [i.id for i in folders.items] == ["albums", "album-1", "album-2"]
    scoped = await service.search_page(
        MOCK_SERVER.id, "track", "tracks", "album-1", 1, 1
    )
    assert [i.id for i in scoped.items] == ["a1-t2"]
    assert scoped.total_matches == 3
    with pytest.raises(DlnaBrowseError) as exc:
        await client.search(MOCK_SERVER, "nope", TITLE, 0, 10)
    assert exc.value.error_code == "710"
