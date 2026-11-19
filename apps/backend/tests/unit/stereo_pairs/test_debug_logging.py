"""Debug logging that makes the stereo pair protocol visible on a real speaker.

The speaker/Marge traffic and the raw zone/group WebSocket events are logged so a
capture from real hardware can be read from the container log.
"""

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_stereo_pair_service
from opencloudtouch.core.logging import clip_for_log
from opencloudtouch.devices.websocket.connection import DeviceWebSocket
from opencloudtouch.main import app
from opencloudtouch.stereo_pairs import group_client
from opencloudtouch.stereo_pairs.group_client import HttpGroupClient
from opencloudtouch.stereo_pairs.repository import StereoPair


class TestClipForLog:
    def test_short_text_is_unchanged(self):
        assert clip_for_log("<a/>") == "<a/>"

    def test_long_text_is_cut_and_marked(self):
        clipped = clip_for_log("x" * 50, limit=10)
        assert clipped.startswith("x" * 10)
        assert "40 more" in clipped

    def test_collapses_whitespace_so_one_message_is_one_log_line(self):
        assert clip_for_log("<a>\n  <b/>\n</a>") == "<a> <b/> </a>"

    def test_none_becomes_empty(self):
        assert clip_for_log(None) == ""


@pytest.fixture
def speaker(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'<group id="7"><name>x</name></group>')

    real = httpx.AsyncClient
    monkeypatch.setattr(
        group_client.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )


@pytest.mark.asyncio
async def test_speaker_request_and_response_are_logged(speaker, caplog):
    caplog.set_level(logging.DEBUG, logger="opencloudtouch.stereo_pairs.group_client")

    await HttpGroupClient("10.0.0.1").add_group(
        "Office", "L1", {"L1": ("LEFT", "10.0.0.1"), "R1": ("RIGHT", "10.0.0.2")}
    )

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "[SPEAKER] -> POST 10.0.0.1 /addGroup" in text
    assert "<masterDeviceId>L1</masterDeviceId>" in text
    assert "[SPEAKER] <- 200 10.0.0.1 /addGroup" in text
    assert '<group id="7">' in text


@pytest.mark.asyncio
async def test_speaker_failure_is_logged_too(monkeypatch, caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    real = httpx.AsyncClient
    monkeypatch.setattr(
        group_client.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    caplog.set_level(logging.DEBUG, logger="opencloudtouch.stereo_pairs.group_client")

    client = HttpGroupClient("10.0.0.1")
    with pytest.raises(group_client.GroupClientError):
        await client.get_group()

    assert any(
        "[SPEAKER] !! 10.0.0.1 /getGroup" in r.getMessage() for r in caplog.records
    )


GROUP_BODY = (
    b"<group><masterDeviceId>L1</masterDeviceId><name>Office</name><roles>"
    b"<groupRole><deviceId>L1</deviceId><role>LEFT</role></groupRole>"
    b"<groupRole><deviceId>R1</deviceId><role>RIGHT</role></groupRole>"
    b"</roles></group>"
)


@pytest.fixture
def marge_client():
    service = MagicMock()
    service.marge_create = AsyncMock(
        return_value=StereoPair(7, "Office", "L1", "L1", "R1", datetime.now(UTC))
    )
    service.marge_dissolve = AsyncMock()
    app.dependency_overrides[get_stereo_pair_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.pop(get_stereo_pair_service, None)


def test_marge_group_requests_are_logged_with_body_and_status(marge_client, caplog):
    caplog.set_level(logging.DEBUG, logger="opencloudtouch.marge.routes")

    marge_client.post("/streaming/account/123/group/", content=GROUP_BODY)
    marge_client.delete("/streaming/account/123/group/7")

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "[MARGE/GROUP] POST /streaming/account/123/group/" in text
    assert "<masterDeviceId>L1</masterDeviceId>" in text
    assert "-> 201" in text
    assert "[MARGE/GROUP] DELETE /streaming/account/123/group/7" in text
    assert "-> 200" in text


def _ws() -> DeviceWebSocket:
    return DeviceWebSocket(
        device_id="AA", ip="1.2.3.4", on_event=AsyncMock(), on_state_change=AsyncMock()
    )


async def _listen(ws: DeviceWebSocket, *messages: str) -> None:
    mock_ws = AsyncMock()

    async def messages_iter():
        for message in messages:
            yield message

    mock_ws.__aiter__ = lambda self: messages_iter()
    ws._ws = mock_ws
    ws._should_run = True
    await ws._listen_loop()


ZONE = '<updates deviceID="AA"><zoneUpdated/></updates>'
GROUP_EVENT = (
    '<updates deviceID="AA"><groupUpdated><group id="7"><name>Office</name>'
    "</group></groupUpdated></updates>"
)
VOLUME = (
    '<updates deviceID="AA"><volumeUpdated deviceID="AA"><volume>'
    "<targetvolume>1</targetvolume><actualvolume>1</actualvolume>"
    "<muteenabled>false</muteenabled></volume></volumeUpdated></updates>"
)


@pytest.mark.asyncio
async def test_raw_group_and_zone_events_are_logged(caplog):
    caplog.set_level(
        logging.DEBUG, logger="opencloudtouch.devices.websocket.connection"
    )

    await _listen(_ws(), ZONE, GROUP_EVENT)

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert 'ws.raw AA <updates deviceID="AA"><zoneUpdated/></updates>' in text
    assert "<groupUpdated>" in text


@pytest.mark.asyncio
async def test_routine_events_do_not_log_raw_xml(caplog):
    caplog.set_level(
        logging.DEBUG, logger="opencloudtouch.devices.websocket.connection"
    )

    await _listen(_ws(), VOLUME)

    assert not any("ws.raw" in r.getMessage() for r in caplog.records)
