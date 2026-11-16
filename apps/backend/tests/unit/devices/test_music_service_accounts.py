"""Device client methods for media server accounts: adapter and mock client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.adapter import BoseDeviceClientAdapter
from opencloudtouch.devices.client import SpeakerCommandError
from opencloudtouch.devices.mock_client import MockDeviceClient

USER = "5f9ec1b3-ed59-4f22-9c2e-1d3a7b8c4e01/0"
SOURCES_XML = (
    '<sources deviceID="X">'
    '<sourceItem source="STORED_MUSIC" sourceAccount="{u}" status="READY"/>'
    '<sourceItem source="AUX" sourceAccount="AUX" status="READY"/></sources>'
).format(u=USER)


@pytest.fixture
def adapter():
    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice",
        return_value=MagicMock(),
    ):
        return BoseDeviceClientAdapter("http://192.0.2.10:8090")


def _http(response=None, error=None):
    cls = patch("httpx.AsyncClient")
    started = cls.start()
    client = AsyncMock()
    started.return_value.__aenter__.return_value = client
    for verb in ("get", "post"):
        if error:
            getattr(client, verb).side_effect = error
        else:
            getattr(client, verb).return_value = response
    return cls, client


def _response(status=200, text=""):
    r = MagicMock()
    r.status_code, r.text = status, text
    r.raise_for_status = MagicMock()
    return r


async def test_get_source_list_parses_items(adapter):
    cls, _ = _http(_response(text=SOURCES_XML))
    try:
        sources = await adapter.get_source_list()
    finally:
        cls.stop()
    assert [(s.source, s.account, s.status) for s in sources] == [
        ("STORED_MUSIC", USER, "READY"),
        ("AUX", "AUX", "READY"),
    ]


async def test_get_source_list_unreachable(adapter):
    cls, _ = _http(error=OSError("down"))
    try:
        with pytest.raises(DeviceConnectionError):
            await adapter.get_source_list()
    finally:
        cls.stop()


async def test_set_account_sends_credentials_and_escapes(adapter):
    cls, client = _http(_response())
    try:
        await adapter.set_music_service_account("STORED_MUSIC", 'A "B" <&>', USER)
    finally:
        cls.stop()
    url = client.post.call_args.args[0]
    body = client.post.call_args.kwargs["content"].decode()
    assert url.endswith("/setMusicServiceAccount")
    assert 'displayName="A &quot;B&quot; &lt;&amp;&gt;"' in body
    assert f"<user>{USER}</user><pass/>" in body


@pytest.mark.parametrize("path", ["set", "remove"])
async def test_account_command_error_carries_speaker_code(adapter, path):
    answer = _response(400, '<errors><error value="1022" name="x" severity="Error"/></errors>')
    cls, _ = _http(answer)
    method = getattr(adapter, f"{path}_music_service_account")
    try:
        with pytest.raises(SpeakerCommandError) as err:
            await method("STORED_MUSIC", "n", USER)
    finally:
        cls.stop()
    assert err.value.error_code == 1022


async def test_account_command_error_without_code(adapter):
    cls, _ = _http(_response(500, "not xml"))
    try:
        with pytest.raises(SpeakerCommandError) as err:
            await adapter.remove_music_service_account("STORED_MUSIC", "n", USER)
    finally:
        cls.stop()
    assert err.value.error_code is None


async def test_account_command_unreachable(adapter):
    cls, _ = _http(error=OSError("down"))
    try:
        with pytest.raises(DeviceConnectionError):
            await adapter.set_music_service_account("STORED_MUSIC", "n", USER)
    finally:
        cls.stop()


# ---- mock client ---------------------------------------------------------------------


@pytest.fixture
def mock():
    MockDeviceClient.reset_sources()
    yield MockDeviceClient("AABBCC112233")
    MockDeviceClient.reset_sources()
    MockDeviceClient.on_register = None


async def test_mock_registration_is_ready_without_reboot(mock):
    seen = []

    async def on_register(*args):
        seen.append(args)

    MockDeviceClient.on_register = on_register
    await mock.set_music_service_account("STORED_MUSIC", "Music", USER)
    assert [(s.account, s.status) for s in await mock.get_source_list()] == [(USER, "READY")]
    assert seen == [("AABBCC112233", USER.split("/")[0], "Music", 7)]
    # state is shared between client instances (a client is created per call)
    assert len(await MockDeviceClient("AABBCC112233").get_source_list()) == 1


async def test_mock_stale_provider_shows_up_after_reboot(mock):
    MockDeviceClient.provider_id = 50
    await mock.set_music_service_account("STORED_MUSIC", "Music", USER)
    assert await mock.get_source_list() == []
    await mock.reboot()
    assert len(await mock.get_source_list()) == 1


async def test_mock_remove_answers_like_the_speaker(mock):
    with pytest.raises(SpeakerCommandError) as err:
        await mock.remove_music_service_account("STORED_MUSIC", "n", USER)
    assert err.value.error_code == 1047
    await mock.set_music_service_account("STORED_MUSIC", "n", USER)
    with pytest.raises(SpeakerCommandError) as dup:
        await mock.set_music_service_account("STORED_MUSIC", "n", USER)
    assert dup.value.error_code == 1022
    await mock.remove_music_service_account("STORED_MUSIC", "n", USER.upper())
    assert await mock.get_source_list() == []
