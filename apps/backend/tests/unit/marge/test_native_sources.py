"""Native STORED_MUSIC sources in the Marge emulation (AC-A1 .. A8, A11 .. A14, A16).

Real service and repositories on a temporary database, only the device lookup is
a fake. The ids below are made up (documentation-style UUIDs and MACs).
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock
from xml.etree import ElementTree as ET

import httpx
import pytest

from opencloudtouch.core.dependencies import get_marge_service
from opencloudtouch.main import app
from opencloudtouch.marge.service import MargeService
from opencloudtouch.marge.source_repository import MargeSourceRepository
from opencloudtouch.marge.xml_builder import (
    build_recent_response_xml,
    build_recents_response_xml,
    build_streaming_account_xml,
)
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.recents.models import RecentPlay

SERVER_A = "11111111-2222-3333-4444-555555555555"
SERVER_B = "66666666-7777-8888-9999-aaaaaaaaaaaa"
ACCOUNT_1 = "acc-0001"
DEV1, DEV2 = "AABBCCDDEE01", "AABBCCDDEE02"
SECRET_NAME = "Secret Living Room Name"
DEVICE_URL = "/streaming/account/{}/device"


class FakeDevices:
    """account uuid -> device, plus the account == device id fallback."""

    def __init__(self):
        self.by_account = {
            ACCOUNT_1: SimpleNamespace(device_id=DEV1, name="Kitchen Speaker"),
            "acc-0002": SimpleNamespace(device_id=DEV2, name="Bedroom Speaker"),
        }
        self.by_id = {
            DEV1: self.by_account[ACCOUNT_1],
            DEV2: self.by_account["acc-0002"],
        }

    async def get_by_account_uuid(self, account_id):
        return self.by_account.get(account_id)

    async def get_by_device_id(self, device_id):
        return self.by_id.get(device_id)


@pytest.fixture
async def env(tmp_path):
    sources = MargeSourceRepository(tmp_path / "t.db")
    await sources.initialize()
    presets = PresetRepository(tmp_path / "t.db")
    await presets.initialize()
    recents = AsyncMock()
    recents.get_recents.return_value = []
    service = MargeService(presets, recents, FakeDevices(), sources)
    app.dependency_overrides[get_marge_service] = lambda: service
    yield SimpleNamespace(service=service, sources=sources, presets=presets)
    app.dependency_overrides.pop(get_marge_service, None)
    await sources.close()
    await presets.close()


@pytest.fixture
async def client(env):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


def xml(response):
    return ET.fromstring(response.text)


# ---- provider ids (AC-A1, A2) -------------------------------------------------


async def test_sourceproviders_lists_7_and_never_50(client):
    response = await client.get("/streaming/sourceproviders")
    ids = {
        p.findtext("name"): p.get("id") for p in xml(response).findall("sourceprovider")
    }
    assert ids["STORED_MUSIC"] == "7"
    assert "50" not in ids.values()


async def test_full_without_rows_only_changes_the_provider_id(client):
    response = await client.get(f"/streaming/account/{ACCOUNT_1}/full")
    sources = xml(response).find("sources").findall("source")
    stored = [s for s in sources if s.findtext("sourcename") == "STORED_MUSIC"]
    assert len(stored) == 1
    assert stored[0].get("id") == "7"
    assert stored[0].findtext("sourceproviderid") == "7"
    assert len(sources) == 9
    assert ">50<" not in response.text and 'id="50"' not in response.text


# ---- POST device (pairing handshake, Amendment 2) --------------------------------


def device_body(device=DEV1, extra=""):
    return f'<device deviceid="{device}">{extra}<name>x</name></device>'.encode()


@pytest.mark.parametrize("suffix", ["/", ""])
async def test_device_handshake_answers_201_and_stores_nothing(client, env, suffix):
    response = await client.post(
        DEVICE_URL.format(ACCOUNT_1) + suffix, content=device_body()
    )
    assert response.status_code == 201
    assert "streaming-v1.2" in response.headers["content-type"]
    root = xml(response)
    assert root.tag == "device" and root.get("deviceid") == DEV1
    assert [c.tag for c in root] == ["createdOn", "ipaddress", "name", "updatedOn"]
    assert await env.sources.count_for_device(DEV1) == 0


async def test_device_account_equal_to_device_id_is_found_by_fallback(client):
    response = await client.post(DEVICE_URL.format(DEV2), content=device_body(DEV2))
    assert response.status_code == 201


async def test_device_unknown_account_is_404(client):
    response = await client.post(DEVICE_URL.format("nobody"), content=device_body())
    assert response.status_code == 404


async def test_device_of_another_account_is_404(client):
    response = await client.post(
        DEVICE_URL.format(ACCOUNT_1), content=device_body(DEV2)
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        b"not xml",
        b"<other/>",
        b"<device/>",
        b'<device deviceid=""/>',
        b'<!DOCTYPE d [<!ENTITY e "x">]><device deviceid="&e;"/>',
    ],
)
async def test_device_invalid_input_is_400(client, payload):
    response = await client.post(DEVICE_URL.format(ACCOUNT_1), content=payload)
    assert response.status_code == 400
    assert response.content == b""


async def test_device_declared_oversize_body_is_413(client):
    response = await client.post(
        DEVICE_URL.format(ACCOUNT_1), content=device_body(extra="x" * 5000)
    )
    assert response.status_code == 413


async def test_device_chunked_oversize_body_is_413(client):
    async def chunks():
        for _ in range(10):
            yield b"x" * 1000

    response = await client.post(DEVICE_URL.format(ACCOUNT_1), content=chunks())
    assert response.status_code == 413


async def test_source_routes_are_gone(client):
    url = f"/streaming/account/{ACCOUNT_1}/source"
    assert (await client.post(url, content=b"<source/>")).status_code in (404, 405)
    assert (await client.delete(f"{url}/1")).status_code in (404, 405)


# ---- /full with rows (AC-A8) ----------------------------------------------------


async def test_full_lists_per_server_sources_and_drops_the_generic_one(client, env):
    a = await env.sources.upsert(DEV1, SERVER_A, "Music")
    b = await env.sources.upsert(DEV1, SERVER_B, "Other")
    await env.sources.upsert(DEV1, "00000000-0000-0000-0000-000000000009", "x")
    await env.sources.delete(DEV1, "00000000-0000-0000-0000-000000000009")
    await env.sources.upsert(DEV2, "00000000-0000-0000-0000-000000000008", "y")

    response = await client.get(f"/streaming/account/{ACCOUNT_1}/full")

    root = xml(response)
    assert root.tag == "account"
    sources = root.find("sources").findall("source")
    media = [s for s in sources if s.findtext("sourcename") == "Mediaserver"]
    assert [m.get("id") for m in media] == [str(a.source_id), str(b.source_id)]
    first = media[0]
    assert first.get("type") == "Audio"
    assert first.find("credential").get("type") == "token"
    assert first.findtext("name") == f"{SERVER_A}/0"
    assert first.findtext("username") == f"{SERVER_A}/0"
    assert first.findtext("sourceproviderid") == "7"
    assert first.find("sourceSettings") is not None
    assert not [s for s in sources if s.findtext("sourcename") == "STORED_MUSIC"]
    assert len(sources) == 8 + 2  # nine base sources minus generic plus two rows


# ---- store call (AC-A11) --------------------------------------------------------


def preset_put(sourceid, location="obj-1", ctype="dir"):
    return (
        f'<preset buttonNumber="2"><sourceid>{sourceid}</sourceid><name>Album</name>'
        f"<location>{location}</location>"
        f"<contentItemType>{ctype}</contentItemType></preset>"
    )


async def test_preset_put_with_registered_id_stores_the_native_representation(
    client, env
):
    row = await env.sources.upsert(DEV1, SERVER_A, "Music")
    response = await client.put(
        f"/streaming/account/{ACCOUNT_1}/device/{DEV1}/preset/2",
        content=preset_put(row.source_id),
    )
    assert response.status_code == 200
    stored = await env.presets.get_preset(DEV1, 2)
    assert stored.source == "DLNA"
    assert stored.station_url == f"dlna://{SERVER_A}/obj-1"
    assert stored.station_uuid.startswith("dlna-")
    assert stored.native_type == "dir"
    # round trip: the answer carries the registered source and the object id
    entry = xml(response)
    assert entry.findtext("sourceid") == str(row.source_id)
    assert entry.findtext("location") == "obj-1"
    assert entry.find("source").get("id") == str(row.source_id)


async def test_preset_put_native_track_type_is_kept(client, env):
    row = await env.sources.upsert(DEV1, SERVER_A, "Music")
    await client.put(
        f"/streaming/account/{ACCOUNT_1}/device/{DEV1}/preset/2",
        content=preset_put(row.source_id, ctype="track"),
    )
    assert (await env.presets.get_preset(DEV1, 2)).native_type == "track"


async def test_preset_put_with_unregistered_numeric_id_behaves_as_before(client, env):
    response = await client.put(
        f"/streaming/account/{ACCOUNT_1}/device/{DEV1}/preset/2",
        content=preset_put("31337", location="http://x/stream"),
    )
    assert response.status_code == 200
    stored = await env.presets.get_preset(DEV1, 2)
    assert stored.source == "31337" and stored.native_type is None


async def test_preset_put_alias_50_is_stored_as_stored_music(client, env):
    await client.put(
        f"/streaming/account/{ACCOUNT_1}/device/{DEV1}/preset/2",
        content=preset_put("50", location="obj-1"),
    )
    assert (await env.presets.get_preset(DEV1, 2)).source == "STORED_MUSIC"


async def test_preset_put_with_a_foreign_account_is_404_and_stores_nothing(client, env):
    row = await env.sources.upsert(DEV1, SERVER_A, "Music")
    foreign = await client.put(
        f"/streaming/account/acc-0002/device/{DEV1}/preset/2",
        content=preset_put(row.source_id),
    )
    other_device = await client.put(
        f"/streaming/account/acc-0002/device/{DEV2}/preset/2",
        content=preset_put(row.source_id),
    )
    assert foreign.status_code == 404 and other_device.status_code == 404
    assert await env.presets.get_preset(DEV1, 2) is None
    assert await env.presets.get_preset(DEV2, 2) is None


# ---- recents (AC-A12) -----------------------------------------------------------


def recent_post(sourceid):
    return (
        f"<recent><sourceid>{sourceid}</sourceid><name>Album</name>"
        "<location>obj-9</location></recent>"
    )


@pytest.mark.parametrize(
    "sourceid,expected", [("50", "STORED_MUSIC"), ("7", "STORED_MUSIC")]
)
async def test_recent_with_legacy_or_real_provider_is_stored_as_stored_music(
    client, env, sourceid, expected
):
    env.service._recents_repo.add_recent.side_effect = lambda r: _with_id(r)
    response = await client.post(
        f"/streaming/account/{ACCOUNT_1}/device/{DEV1}/recent",
        content=recent_post(sourceid),
    )
    assert response.status_code == 201
    assert env.service._recents_repo.add_recent.await_args.args[0].source == expected
    assert xml(response).findtext("sourceid") == "7"
    assert 'id="50"' not in response.text and ">50<" not in response.text


async def test_recent_with_registered_numeric_id_is_stored_unchanged(client, env):
    row = await env.sources.upsert(DEV1, SERVER_A, "Music")
    env.service._recents_repo.add_recent.side_effect = lambda r: _with_id(r)
    response = await client.post(
        f"/streaming/account/{ACCOUNT_1}/device/{DEV1}/recent",
        content=recent_post(row.source_id),
    )
    assert response.status_code == 201
    assert env.service._recents_repo.add_recent.await_args.args[0].source == str(
        row.source_id
    )
    root = xml(response)
    assert root.findtext("sourceid") == str(row.source_id)
    assert root.find("source").get("id") == str(row.source_id)


def _with_id(recent):
    recent.id = 5
    return recent


def _recent(source):
    return RecentPlay(device_id=DEV1, source=source, location="obj", name="n", id=3)


def _row(env_rows):
    return env_rows


@pytest.fixture
async def one_row(env):
    return await env.sources.upsert(DEV1, SERVER_A, "Music")


async def test_recent_builders_follow_the_documented_cases(one_row):
    rows = [one_row]
    registered = build_recent_response_xml(_recent(str(one_row.source_id)), rows)
    assert registered.findtext("sourceid") == str(one_row.source_id)
    assert registered.find("source").get("id") == str(one_row.source_id)

    legacy_with_rows = build_recent_response_xml(_recent("STORED_MUSIC"), rows)
    assert legacy_with_rows.findtext("sourceid") == "7"
    assert legacy_with_rows.find("source") is None

    legacy_without = build_recent_response_xml(_recent("STORED_MUSIC"))
    assert legacy_without.findtext("sourceid") == "7"
    assert legacy_without.find("source").get("id") == "7"

    unknown = build_recent_response_xml(_recent("424242"), rows)
    assert unknown.findtext("sourceid") == "" and unknown.find("source") is None

    listed = build_recents_response_xml(
        [_recent(str(one_row.source_id)), _recent("STORED_MUSIC"), _recent("424242")],
        rows,
    )
    entries = listed.findall("recent")
    assert [e.findtext("sourceid") for e in entries] == [
        str(one_row.source_id),
        "7",
        "",
    ]
    assert entries[0].find("source").get("id") == str(one_row.source_id)
    assert entries[1].find("source") is None


# ---- preset XML (AC-A13) --------------------------------------------------------


def _native_preset():
    return Preset(
        DEV1,
        2,
        "dlna-x",
        "Album",
        f"dlna://{SERVER_A}/obj-1",
        source="DLNA",
        native_type="dir",
    )


async def test_native_preset_with_row_is_a_native_entry(one_row):
    account = build_streaming_account_xml(
        ACCOUNT_1, DEV1, [_native_preset()], None, [one_row]
    )
    entry = account.find("devices/device/presets/preset")
    assert entry.findtext("location") == "obj-1"
    assert entry.findtext("contentItemType") == "dir"
    assert entry.findtext("sourceid") == str(one_row.source_id)
    assert entry.find("source").get("id") == str(one_row.source_id)
    assert entry.findtext("username") == ""


async def test_native_preset_without_row_keeps_the_v1_location():
    account = build_streaming_account_xml(ACCOUNT_1, DEV1, [_native_preset()], None, [])
    entry = account.find("devices/device/presets/preset")
    assert "orion/station?data=" in entry.findtext("location")
    assert entry.findtext("contentItemType") == "stationurl"
    assert entry.find("sourceid") is None


async def test_presets_route_ignores_native_type_without_rows(env):
    from opencloudtouch.marge.xml_builder import build_presets_xml

    item = build_presets_xml([_native_preset()]).find("preset/ContentItem")
    assert item.get("source") == "LOCAL_INTERNET_RADIO"
    assert item.get("type") == "stationurl"


# ---- logging (AC-A14) -----------------------------------------------------------


async def test_device_route_logs_no_body_no_names(client, env, caplog):
    caplog.set_level(logging.DEBUG)
    await client.post(
        DEVICE_URL.format(ACCOUNT_1),
        content=device_body(extra=f"<ip>{SECRET_NAME}</ip>"),
    )
    await client.post(DEVICE_URL.format(ACCOUNT_1), content=b"<broken")
    at_info = "\n".join(
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.INFO and r.name.startswith("opencloudtouch")
    )
    assert "[MARGE/DEVICE]" in at_info
    for forbidden in (SECRET_NAME, "Kitchen Speaker", "<device", "<broken"):
        assert forbidden not in at_info
