"""Tests for SoundTouch UPnP renderer control."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from opencloudtouch.dlna.renderer import DlnaRenderer, DlnaRendererError


@pytest.mark.asyncio
async def test_play_uri():
    renderer = DlnaRenderer()

    response = MagicMock()
    response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.post.return_value = response

    with patch("opencloudtouch.dlna.renderer.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__.return_value = client

        await renderer.play_uri(
            "192.168.55.26",
            "http://192.168.55.4:8200/MediaItems/24.mp3",
        )

    args, kwargs = client.post.await_args

    assert args[0] == "http://192.168.55.26:8091/AVTransport/Control"
    assert "SetAVTransportURI" in kwargs["content"]
    assert (
        "<CurrentURI>"
        "http://192.168.55.4:8200/MediaItems/24.mp3"
        "</CurrentURI>" in kwargs["content"]
    )
    assert (
        kwargs["headers"]["SOAPAction"]
        == '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"'
    )


@pytest.mark.asyncio
async def test_pause():
    renderer = DlnaRenderer()

    with patch.object(renderer, "_send_action", new_callable=AsyncMock) as send:
        await renderer.pause("192.168.55.26")

    send.assert_awaited_once()
    assert send.await_args.args[0] == "192.168.55.26"
    assert send.await_args.args[1] == "Pause"


@pytest.mark.asyncio
async def test_resume():
    renderer = DlnaRenderer()

    with patch.object(renderer, "_send_action", new_callable=AsyncMock) as send:
        await renderer.resume("192.168.55.26")

    send.assert_awaited_once()
    assert send.await_args.args[1] == "Play"


@pytest.mark.asyncio
async def test_renderer_error():
    renderer = DlnaRenderer()

    client = AsyncMock()
    client.post.side_effect = Exception("boom")

    with patch("opencloudtouch.dlna.renderer.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__.return_value = client

        with pytest.raises(Exception):
            await renderer.play_uri(
                "192.168.55.26",
                "http://example.test/song.mp3",
            )


def test_escape_xml():
    assert DlnaRenderer._escape_xml("a&b<c>") == "a&amp;b&lt;c&gt;"


@pytest.mark.asyncio
async def test_subscribe(respx_mock):
    route = respx_mock.request(
        method="SUBSCRIBE",
        url="http://192.0.2.10:8091/AVTransport/Event",
    ).mock(
        return_value=httpx.Response(
            200,
            headers={
                "SID": "uuid:test-subscription",
                "TIMEOUT": "Second-300",
            },
        )
    )

    renderer = DlnaRenderer()

    sid, timeout = await renderer.subscribe(
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )

    assert route.called
    request = route.calls.last.request

    assert request.headers["CALLBACK"] == (
        "<http://192.0.2.20:7777/api/dlna/events/device-1>"
    )
    assert request.headers["NT"] == "upnp:event"
    assert request.headers["TIMEOUT"] == "Second-300"
    assert sid == "uuid:test-subscription"
    assert timeout == 300


@pytest.mark.asyncio
async def test_renew_subscription(respx_mock):
    route = respx_mock.request(
        method="SUBSCRIBE",
        url="http://192.0.2.10:8091/AVTransport/Event",
    ).mock(
        return_value=httpx.Response(
            200,
            headers={
                "SID": "uuid:test-subscription",
                "TIMEOUT": "Second-300",
            },
        )
    )

    renderer = DlnaRenderer()

    sid, timeout = await renderer.renew_subscription(
        "192.0.2.10",
        "uuid:test-subscription",
        300,
    )

    assert route.called
    request = route.calls.last.request

    assert request.headers["SID"] == "uuid:test-subscription"
    assert request.headers["TIMEOUT"] == "Second-300"
    assert "CALLBACK" not in request.headers
    assert "NT" not in request.headers
    assert sid == "uuid:test-subscription"
    assert timeout == 300


@pytest.mark.asyncio
async def test_unsubscribe(respx_mock):
    route = respx_mock.request(
        method="UNSUBSCRIBE",
        url="http://192.0.2.10:8091/AVTransport/Event",
    ).mock(return_value=httpx.Response(200))

    renderer = DlnaRenderer()

    await renderer.unsubscribe(
        "192.0.2.10",
        "uuid:test-subscription",
    )

    assert route.called
    assert route.calls.last.request.headers["SID"] == "uuid:test-subscription"


@pytest.mark.asyncio
async def test_get_source(respx_mock):
    route = respx_mock.get("http://192.0.2.10:8090/now_playing").mock(
        return_value=httpx.Response(
            200,
            text='<nowPlaying deviceID="test" source="UPNP" />',
        )
    )

    source = await DlnaRenderer().get_source("192.0.2.10")

    assert route.called
    assert source == "UPNP"


@pytest.mark.asyncio
@pytest.mark.parametrize("xml", ["<broken", '<nowPlaying deviceID="test" />'])
async def test_get_source_rejects_invalid_or_missing_source(respx_mock, xml):
    respx_mock.get("http://192.0.2.10:8090/now_playing").mock(
        return_value=httpx.Response(200, text=xml)
    )

    if xml == "<broken":
        with pytest.raises(DlnaRendererError, match="source query failed"):
            await DlnaRenderer().get_source("192.0.2.10")
    else:
        assert await DlnaRenderer().get_source("192.0.2.10") == ""
