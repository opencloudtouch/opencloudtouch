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


async def test_pair_sends_the_account_and_expects_info(adapter):
    cls, client = _http(_response(text='<info deviceID="X"></info>'))
    try:
        await adapter.pair_with_account("acct<1>")
    finally:
        cls.stop()
    url = client.post.call_args.args[0]
    body = client.post.call_args.kwargs["content"].decode()
    assert url.endswith("/setMargeAccount")
    assert body == (
        "<PairDeviceWithAccount><accountId>acct&lt;1&gt;</accountId>"
        "<userAuthToken>local</userAuthToken></PairDeviceWithAccount>"
    )


async def test_pair_error_carries_the_speaker_code(adapter):
    answer = _response(
        500, '<errors><error value="1038" name="x" severity="Error"/></errors>'
    )
    cls, _ = _http(answer)
    try:
        with pytest.raises(SpeakerCommandError) as err:
            await adapter.pair_with_account("acct")
    finally:
        cls.stop()
    assert err.value.error_code == 1038


async def test_pair_without_info_answer_is_an_error(adapter):
    cls, _ = _http(_response(200, "<other/>"))
    try:
        with pytest.raises(SpeakerCommandError) as err:
            await adapter.pair_with_account("acct")
    finally:
        cls.stop()
    assert err.value.error_code is None


async def test_pair_unreachable(adapter):
    cls, _ = _http(error=OSError("down"))
    try:
        with pytest.raises(DeviceConnectionError):
            await adapter.pair_with_account("acct")
    finally:
        cls.stop()


# ---- mock client ---------------------------------------------------------------------


@pytest.fixture
def mock():
    MockDeviceClient.reset_sources()

    async def listed(device_id):
        return [USER]

    MockDeviceClient.listed_accounts = listed
    yield MockDeviceClient("AABBCC112233")
    MockDeviceClient.reset_sources()


async def test_mock_lists_the_servers_oct_lists(mock):
    assert [(s.account, s.status) for s in await mock.get_source_list()] == [
        (USER, "READY")
    ]


async def test_mock_stale_speaker_lists_nothing_until_re_paired(mock):
    MockDeviceClient.stale_devices.add("AABBCC112233")
    assert await mock.get_source_list() == []
    await MockDeviceClient("AABBCC112233").pair_with_account("acct")
    assert MockDeviceClient.pair_calls == ["acct"]
    assert len(await mock.get_source_list()) == 1


async def test_mock_without_hook_lists_nothing():
    MockDeviceClient.reset_sources()
    assert await MockDeviceClient("AABBCC112233").get_source_list() == []
