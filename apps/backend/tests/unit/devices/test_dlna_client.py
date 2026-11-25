"""Speaker-side DLNA read calls: listMediaServers, STORED_MUSIC navigate, sources."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.client import SpeakerSource
from opencloudtouch.devices.client_adapter import BoseDeviceClientAdapter
from opencloudtouch.devices.mock_client import MockDeviceClient

FIXTURES = Path(__file__).parent / "fixtures"
UDN = "4D696E69-0000-0000-0000-00000000000A"
ACCOUNT = f"{UDN}/0"
ERROR_1005 = (
    '<errors deviceID="000000000000"><error value="1005" '
    'name="UNKNOWN_SOURCE_ERROR" severity="Unknown">1005</error></errors>'
)


def fx(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _response(text: str = "", status: int = 200) -> httpx.Response:
    request = httpx.Request("GET", "http://192.0.2.50:8090/x")
    return httpx.Response(status, text=text, request=request)


@pytest.fixture
def adapter():
    with patch("opencloudtouch.devices.client_adapter.SoundTouchDevice"):
        return BoseDeviceClientAdapter("http://192.0.2.50:8090")


@pytest.fixture
def http():
    """Patched httpx.AsyncClient; yields the client whose get/post are AsyncMocks."""
    with patch("httpx.AsyncClient") as cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        cls.return_value = client
        yield client


async def test_list_media_servers_keeps_case(adapter, http):
    http.get.return_value = _response(fx("list_media_servers.xml"))

    assert await adapter.list_media_servers() == [
        UDN,
        "4d696e69-0000-0000-0000-00000000000b",
    ]
    assert http.get.call_args.args[0] == "http://192.0.2.50:8090/listMediaServers"


async def test_browse_parses_folder_items_verbatim(adapter, http):
    http.post.return_value = _response(fx("navigate_folder.xml"))

    result = await adapter.browse_stored_music(ACCOUNT, "117634")

    assert http.post.call_args.args[0] == "http://192.0.2.50:8090/navigate"
    body = http.post.call_args.kwargs["content"]
    assert f'<navigate source="STORED_MUSIC" sourceAccount="{ACCOUNT}">' in body
    assert f'location="117634" sourceAccount="{ACCOUNT}"' in body
    assert result.error_code is None
    folder, track = result.items
    assert (folder.name, folder.is_directory, folder.location) == (
        "Album One",
        True,
        "117634",
    )
    assert (track.name, track.is_directory, track.location) == (
        "Track One",
        False,
        "117739 TRACK",
    )
    assert track.source == "STORED_MUSIC"
    assert track.source_account == ACCOUNT
    assert track.item_name == "Track One"


async def test_browse_root_has_no_item(adapter, http):
    http.post.return_value = _response(fx("navigate_folder.xml"))

    await adapter.browse_stored_music(ACCOUNT)

    assert "<item" not in http.post.call_args.kwargs["content"]


async def test_browse_500_errors_body_returns_code(adapter, http):
    http.post.return_value = _response(ERROR_1005, 500)

    result = await adapter.browse_stored_music(ACCOUNT)

    assert (result.items, result.error_code) == ([], 1005)
    assert http.post.await_count == 1


async def test_browse_retries_1602_once_then_ok(adapter, http):
    http.post.side_effect = [
        _response(fx("navigate_error_1602.xml"), 500),
        _response(fx("navigate_folder.xml")),
    ]

    result = await adapter.browse_stored_music(ACCOUNT)

    assert result.error_code is None
    assert len(result.items) == 2
    assert http.post.await_count == 2


async def test_browse_1602_twice_returns_1602(adapter, http):
    http.post.return_value = _response(fx("navigate_error_1602.xml"), 500)

    result = await adapter.browse_stored_music(ACCOUNT)

    assert (result.items, result.error_code) == ([], 1602)
    assert http.post.await_count == 2


@pytest.mark.parametrize(
    "outcome",
    [
        httpx.ConnectError("down"),
        _response("<status/>", 500),
        _response("<not-xml"),
        _response("<errors><error value='x'/></errors>", 500),
    ],
)
async def test_browse_transport_failure_raises(adapter, http, outcome):
    if isinstance(outcome, Exception):
        http.post.side_effect = outcome
    else:
        http.post.return_value = outcome

    with pytest.raises(DeviceConnectionError):
        await adapter.browse_stored_music(ACCOUNT)


async def test_source_list_parses_items(adapter, http):
    http.get.return_value = _response(fx("sources.xml"))

    sources = await adapter.get_source_list()

    assert http.get.call_args.args[0] == "http://192.0.2.50:8090/sources"
    assert sources[:2] == [
        SpeakerSource(
            "STORED_MUSIC",
            "4d696e69-0000-0000-0000-000000000001/0",
            "READY",
            "Music & Albums",
        ),
        SpeakerSource(
            "STORED_MUSIC",
            "4d696e69-0000-0000-0000-000000000002/0",
            "UNAVAILABLE",
            "Offline Library",
        ),
    ]


async def test_source_list_missing_account_empty(adapter, http):
    http.get.return_value = _response(fx("sources.xml"))

    assert (await adapter.get_source_list())[2] == SpeakerSource(
        "AUX", "", "READY", "AUX"
    )


@pytest.mark.parametrize("response", [_response("", 500), _response("<not-xml")])
async def test_read_calls_raise_on_failure(adapter, http, response):
    http.get.return_value = response

    with pytest.raises(DeviceConnectionError):
        await adapter.get_source_list()
    with pytest.raises(DeviceConnectionError):
        await adapter.list_media_servers()


async def test_mock_lists_registered_servers():
    client = MockDeviceClient("AABBCC112233")
    client._media_servers.clear()
    client._media_servers.add(UDN)

    try:
        assert await client.list_media_servers() == [UDN]
        assert await client.get_source_list() == [
            SpeakerSource("AUX", "", "READY", "AUX"),
            SpeakerSource("STORED_MUSIC", ACCOUNT, "READY", UDN),
        ]
        # State is shared per device because the app builds a client per request.
        assert await MockDeviceClient("AABBCC112233").list_media_servers() == [UDN]
        assert (await client.browse_stored_music(ACCOUNT)).items == []
    finally:
        client._media_servers.clear()
