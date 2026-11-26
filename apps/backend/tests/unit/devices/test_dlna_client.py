"""Speaker-side DLNA calls: media servers, navigate, sources, registration, presets."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.client import SpeakerSource, StoredMusicItem
from opencloudtouch.devices.client_adapter import BoseDeviceClientAdapter
from opencloudtouch.devices.mock_client import MockDeviceClient

FIXTURES = Path(__file__).parent / "fixtures"
UDN = "4D696E69-0000-0000-0000-00000000000A"
ACCOUNT = f"{UDN}/0"
ERROR_1005 = (
    '<errors deviceID="000000000000"><error value="1005" '
    'name="UNKNOWN_SOURCE_ERROR" severity="Unknown">1005</error></errors>'
)

ERROR_1047 = (
    '<errors deviceID="000000000000"><error value="1047" '
    'name="SOURCE_ALREADY_REMOVED" severity="Unknown">1047</error></errors>'
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


async def test_browse_uses_long_navigate_timeout(adapter):
    """Large parents take far longer than the 3 s default (T21 4c)."""
    from opencloudtouch.devices.client_adapter import NAVIGATE_TIMEOUT

    with patch("httpx.AsyncClient") as cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        cls.return_value = client
        client.post.return_value = _response(fx("navigate_folder.xml"))
        await adapter.browse_stored_music(ACCOUNT)
        assert cls.call_args.kwargs["timeout"] == NAVIGATE_TIMEOUT > adapter.timeout
        client.get.return_value = _response(fx("list_media_servers.xml"))
        await adapter.list_media_servers()
        assert cls.call_args.kwargs["timeout"] == adapter.timeout


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


async def test_register_body_exact_and_case_kept(adapter, http):
    http.post.return_value = _response("<status>/setMusicServiceAccount</status>")

    await adapter.register_media_server(UDN, 'Rock & "Roll" <1>' + "x" * 70)

    assert (
        http.post.call_args.args[0] == "http://192.0.2.50:8090/setMusicServiceAccount"
    )
    name = 'Rock &amp; "Roll" &lt;1&gt;' + "x" * 47  # cut to 64 chars before escaping
    assert http.post.call_args.kwargs["content"] == (
        f"<credentials source=\"STORED_MUSIC\" displayName='{name}'>"
        f"<user>{UDN}/0</user><pass></pass></credentials>"
    )


@pytest.mark.parametrize(
    "response",
    [
        _response(fx("set_account_error_1022.xml"), 500),
        _response('<error value="1022" name="MARGE_SET_CRED_FAILED"/>'),
    ],
)
async def test_register_error_raises_with_code(adapter, http, response):
    http.post.return_value = response

    with pytest.raises(DeviceConnectionError, match="1022"):
        await adapter.register_media_server(UDN, "Library")


@pytest.mark.parametrize(
    "outcome", [httpx.ConnectError("down"), _response("", 500), _response("<x")]
)
async def test_register_failure_raises(adapter, http, outcome):
    if isinstance(outcome, Exception):
        http.post.side_effect = outcome
    else:
        http.post.return_value = outcome

    with pytest.raises(DeviceConnectionError):
        await adapter.register_media_server(UDN, "Library")


async def test_remove_body(adapter, http):
    http.post.return_value = _response("<status>/removeMusicServiceAccount</status>")

    await adapter.remove_media_server(UDN)

    assert (
        http.post.call_args.args[0]
        == "http://192.0.2.50:8090/removeMusicServiceAccount"
    )
    assert http.post.call_args.kwargs["content"] == (
        '<credentials source="STORED_MUSIC" displayName="">'
        f"<user>{UDN}/0</user><pass></pass></credentials>"
    )


async def test_remove_already_removed_1047_is_success(adapter, http, caplog):
    http.post.return_value = _response(ERROR_1047, 500)

    with caplog.at_level("INFO"):
        await adapter.remove_media_server(UDN)

    assert any("1047" in r.getMessage() for r in caplog.records)


async def test_remove_other_error_still_raises(adapter, http):
    http.post.return_value = _response(ERROR_1005, 500)

    with pytest.raises(DeviceConnectionError, match="1005"):
        await adapter.remove_media_server(UDN)


async def test_notify_body_has_device_id(adapter, http):
    http.post.return_value = _response("<status>/notification</status>")

    await adapter.notify_sources_updated("A0B1C2D3E4F5")

    assert http.post.call_args.args[0] == "http://192.0.2.50:8090/notification"
    assert http.post.call_args.kwargs["content"] == (
        '<updates deviceID="A0B1C2D3E4F5"><sourcesUpdated/></updates>'
    )


@pytest.mark.parametrize(
    "outcome", [httpx.ConnectError("down"), _response("<errors/>", 500)]
)
async def test_notify_failure_swallowed(adapter, http, outcome, caplog):
    if isinstance(outcome, Exception):
        http.post.side_effect = outcome
    else:
        http.post.return_value = outcome

    await adapter.notify_sources_updated("A0B1C2D3E4F5")

    assert any(r.levelname == "WARNING" for r in caplog.records)


ITEM = StoredMusicItem(
    name="Rock & Roll",
    is_directory=True,
    source="STORED_MUSIC",
    location='117634 "a"',
    source_account=ACCOUNT,
    item_name='Rock & "Roll" <1>',
)


async def test_store_native_preset_no_type_escaped(adapter, http):
    http.post.return_value = _response("<presets/>")

    await adapter.store_native_preset(3, ITEM, "http://192.0.2.9/a?b=1&c=2")

    assert http.post.call_args.args[0] == "http://192.0.2.50:8090/storePreset"
    assert http.post.call_args.kwargs["content"] == (
        '<preset id="3" createdOn="0" updatedOn="0">'
        """<ContentItem source="STORED_MUSIC" location='117634 "a"' """
        f'sourceAccount="{ACCOUNT}" isPresetable="true">'
        '<itemName>Rock &amp; "Roll" &lt;1&gt;</itemName>'
        "<containerArt>http://192.0.2.9/a?b=1&amp;c=2</containerArt>"
        "</ContentItem></preset>"
    )


async def test_store_native_preset_artwork_optional_and_name_fallback(adapter, http):
    http.post.return_value = _response("<presets/>")
    item = StoredMusicItem("Album", True, "STORED_MUSIC", "1", ACCOUNT, "")

    await adapter.store_native_preset(1, item)

    body = http.post.call_args.kwargs["content"]
    assert "<itemName>Album</itemName></ContentItem>" in body
    assert "containerArt" not in body
    assert "type" not in body


@pytest.mark.parametrize("slot", [0, 7])
async def test_store_native_preset_invalid_slot(adapter, http, slot):
    with pytest.raises(ValueError):
        await adapter.store_native_preset(slot, ITEM)
    http.post.assert_not_called()


async def test_store_native_preset_http_error_raises(adapter, http):
    http.post.return_value = _response("<errors/>", 500)

    with pytest.raises(DeviceConnectionError):
        await adapter.store_native_preset(1, ITEM)


async def test_mock_register_remove_roundtrip():
    client = MockDeviceClient("AABBCC112233")
    client._media_servers.clear()

    try:
        await client.register_media_server(UDN, "Library")
        assert await MockDeviceClient("AABBCC112233").list_media_servers() == [UDN]
        await client.notify_sources_updated("AABBCC112233")
        await client.remove_media_server(UDN)
        await client.remove_media_server(UDN)
        assert await client.list_media_servers() == []

        await client.store_native_preset(2, ITEM, "art")
        assert client.native_presets == [(2, ITEM, "art")]
        with pytest.raises(ValueError):
            await client.store_native_preset(9, ITEM)
    finally:
        client._media_servers.clear()
