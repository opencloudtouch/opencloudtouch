"""Tests for HttpGroupClient against recorded speaker responses (httpx mock transport)."""

import httpx
import pytest

from opencloudtouch.stereo_pairs import group_client
from opencloudtouch.stereo_pairs.group_client import GroupClientError, HttpGroupClient

INFO = (
    '<?xml version="1.0" encoding="UTF-8" ?><info deviceID="506583CBE338">'
    "<name>Office left</name><type>SoundTouch 10</type>"
    "<margeAccountUUID>3267639</margeAccountUUID><components><component>"
    "<componentCategory>SCM</componentCategory>"
    "<softwareVersion>27.0.6.46330.5043500 epdbuild.trunk</softwareVersion>"
    "</component></components></info>"
)
CAPS = (
    '<capabilities deviceID="X"><lrStereoCapable>true</lrStereoCapable></capabilities>'
)
GROUP = (
    '<group id="7"><name>Office</name><masterDeviceId>L1</masterDeviceId><roles>'
    "<groupRole><deviceId>L1</deviceId><role>LEFT</role></groupRole>"
    "<groupRole><deviceId>R1</deviceId><role>RIGHT</role></groupRole></roles></group>"
)
MARGE_ERROR = (
    '<errors deviceID="X"><error value="5580" '
    'name="GROUP_CREATE_GROUP_ON_MARGE_ERROR" severity="Unknown"> </error></errors>'
)


@pytest.fixture
def speaker(monkeypatch):
    """Install a fake speaker: routes maps path -> body (or an exception)."""
    seen: list[httpx.Request] = []
    routes: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        result = routes[request.url.path]
        if isinstance(result, Exception):
            raise result
        return httpx.Response(200, content=result.encode())

    real = httpx.AsyncClient
    monkeypatch.setattr(
        group_client.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    return routes, seen


@pytest.mark.asyncio
async def test_get_info_parses_identity_firmware_and_capability(speaker):
    routes, _ = speaker
    routes["/info"], routes["/capabilities"] = INFO, CAPS

    info = await HttpGroupClient("10.0.0.1").get_info()

    assert (info.device_id, info.name, info.type) == (
        "506583CBE338",
        "Office left",
        "SoundTouch 10",
    )
    assert info.marge_account_uuid == "3267639"
    assert info.firmware == "27.0.6.46330.5043500"
    assert info.lr_stereo_capable is True


@pytest.mark.asyncio
async def test_empty_group_and_group_with_roles(speaker):
    routes, _ = speaker
    client = HttpGroupClient("10.0.0.1")

    routes["/getGroup"] = '<?xml version="1.0" encoding="UTF-8" ?><group />'
    assert await client.get_group() is None

    routes["/getGroup"] = GROUP
    group = await client.get_group()
    assert (group.id, group.name, group.master_id) == ("7", "Office", "L1")
    assert group.roles == {"L1": "LEFT", "R1": "RIGHT"}


@pytest.mark.asyncio
async def test_zone_members(speaker):
    routes, _ = speaker
    client = HttpGroupClient("10.0.0.1")

    routes["/getZone"] = "<zone />"
    assert await client.get_zone_member_ids() == []

    routes["/getZone"] = (
        '<zone master="A"><member ipaddress="10.0.0.2">B</member></zone>'
    )
    assert await client.get_zone_member_ids() == ["A", "B"]


@pytest.mark.asyncio
async def test_add_group_sends_roles_and_returns_id(speaker):
    routes, seen = speaker
    routes["/addGroup"] = GROUP

    group_id = await HttpGroupClient("10.0.0.2").add_group(
        "A & B",
        "L1",
        {"L1": ("LEFT", "10.0.0.1"), "R1": ("RIGHT", "10.0.0.2")},
        group_id="7",
        sender_ip="10.0.0.1",
    )

    body = seen[-1].content.decode()
    assert group_id == "7"
    assert seen[-1].method == "POST"
    assert '<group id="7">' in body
    assert "<name>A &amp; B</name>" in body
    assert "<role>RIGHT</role>" in body
    assert "<senderIPAddress>10.0.0.1</senderIPAddress>" in body


@pytest.mark.asyncio
async def test_device_error_becomes_coded_certain_error(speaker):
    routes, _ = speaker
    routes["/addGroup"] = MARGE_ERROR

    client = HttpGroupClient("10.0.0.1")
    with pytest.raises(GroupClientError) as raised:
        await client.add_group("n", "L1", {"L1": ("LEFT", "10.0.0.1")})

    assert raised.value.code == "GROUP_CREATE_GROUP_ON_MARGE_ERROR"
    assert raised.value.uncertain is False


@pytest.mark.asyncio
async def test_timeout_is_uncertain_and_bad_xml_is_not(speaker):
    routes, _ = speaker
    client = HttpGroupClient("10.0.0.1")

    routes["/removeGroup"] = httpx.ReadTimeout("slow")
    with pytest.raises(GroupClientError) as raised:
        await client.remove_group()
    assert raised.value.uncertain is True

    routes["/getGroup"] = "not xml"
    with pytest.raises(GroupClientError) as raised:
        await client.get_group()
    assert raised.value.uncertain is False


RENAME_BODY = (
    '<group id="7"><name>Café Stereo</name><masterDeviceId>L1</masterDeviceId>'
    "<roles><groupRole><deviceId>L1</deviceId><role>LEFT</role>"
    "<ipAddress>10.0.0.1</ipAddress></groupRole>"
    "<groupRole><deviceId>R1</deviceId><role>RIGHT</role>"
    "<ipAddress>10.0.0.2</ipAddress></groupRole></roles></group>"
)


@pytest.mark.asyncio
async def test_update_group_posts_the_whole_group(speaker):
    """The speaker answers PUT /updateGroup with 405; the working form is a POST of the whole group."""
    routes, seen = speaker
    routes["/updateGroup"] = GROUP
    client = HttpGroupClient("10.0.0.1")

    await client.update_group(
        "Café Stereo",
        "L1",
        {"L1": ("LEFT", "10.0.0.1"), "R1": ("RIGHT", "10.0.0.2")},
        "7",
    )

    request = seen[0]
    assert request.method == "POST"
    assert request.headers["content-type"] == "application/xml; charset=utf-8"
    assert request.content == RENAME_BODY.encode("utf-8")


@pytest.mark.asyncio
async def test_remove_group_uses_get(speaker):
    routes, seen = speaker
    routes["/removeGroup"] = "<group />"

    await HttpGroupClient("10.0.0.1").remove_group()

    assert [r.method for r in seen] == ["GET"]


NO_GROUP_ERROR = (
    '<errors deviceID="X"><error value="5550" '
    'name="GROUP_NO_GROUP_TO_REMOVE_ERROR" severity="Unknown"> </error></errors>'
)


@pytest.mark.asyncio
async def test_remove_group_without_a_group_is_a_success(speaker):
    """A real speaker answers /removeGroup with 5550 when there is nothing to remove."""
    routes, _ = speaker
    routes["/removeGroup"] = NO_GROUP_ERROR

    await HttpGroupClient("10.0.0.1").remove_group()


@pytest.mark.asyncio
async def test_remove_group_still_raises_for_other_errors(speaker):
    routes, _ = speaker
    routes["/removeGroup"] = MARGE_ERROR

    client = HttpGroupClient("10.0.0.1")
    with pytest.raises(GroupClientError) as caught:
        await client.remove_group()

    assert caught.value.code == "GROUP_CREATE_GROUP_ON_MARGE_ERROR"
