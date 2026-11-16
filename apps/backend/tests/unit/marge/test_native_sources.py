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
SOURCE_URL = "/streaming/account/{}/source"


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


def body(
    server=SERVER_A, provider="7", name="Music", extra="<credential/>", account=None
):
    user = account if account is not None else f"{server}/0"
    return (
        f"<source>{extra}<username>{user}</username>"
        f"<sourceproviderid>{provider}</sourceproviderid>"
        f"<sourcename>{name}</sourcename></source>"
    ).encode()


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


# ---- POST source (AC-A3 .. A6, A16) --------------------------------------------


@pytest.mark.parametrize("provider", ["7", "50"])
async def test_register_answers_201_with_provider_7(client, env, provider):
    response = await client.post(
        SOURCE_URL.format(ACCOUNT_1), content=body(provider=provider)
    )
    assert response.status_code == 201
    assert "streaming-v1.2" in response.headers["content-type"]
    root = xml(response)
    assert int(root.findtext("sourceID")) >= 20000000
    assert root.findtext("sourceProviderID") == "7"
    assert root.findtext("createdOn") and root.findtext("updatedOn")
    rows = await env.sources.list_active(DEV1)
    assert len(rows) == 1
    assert rows[0].received_provider_id == int(provider)


async def test_same_server_twice_gives_same_id_and_one_row(client, env):
    first = await client.post(SOURCE_URL.format(ACCOUNT_1), content=body())
    second = await client.post(
        SOURCE_URL.format(ACCOUNT_1), content=body(server=SERVER_A.upper())
    )
    assert xml(first).findtext("sourceID") == xml(second).findtext("sourceID")
    assert await env.sources.count_for_device(DEV1) == 1


@pytest.mark.parametrize(
    "payload",
    [
        b"not xml",
        b"<other/>",
        body(account=""),
        body(account=SERVER_A),  # no /0
        body(account=f"{SERVER_A}/1"),
        body(account="not-a-uuid/0"),
        body(provider=""),
        body(provider="11"),
        body(name=""),
        body(name="   "),
        body(name="x" * 65),
        b'<!DOCTYPE s [<!ENTITY e "x">]><source><username>&e;</username></source>',
    ],
)
async def test_invalid_input_is_400_and_stores_nothing(client, env, payload):
    response = await client.post(SOURCE_URL.format(ACCOUNT_1), content=payload)
    assert response.status_code == 400
    assert response.content == b""
    assert await env.sources.count_for_device(DEV1) == 0


async def test_unknown_elements_and_credential_are_ignored(client):
    response = await client.post(
        SOURCE_URL.format(ACCOUNT_1),
        content=body(extra="<credential>x</credential><foo>bar</foo>"),
    )
    assert response.status_code == 201


async def test_unknown_account_is_404(client, env):
    response = await client.post(SOURCE_URL.format("nobody"), content=body())
    assert response.status_code == 404


async def test_account_equal_to_device_id_is_found_by_fallback(client, env):
    response = await client.post(SOURCE_URL.format(DEV2), content=body())
    assert response.status_code == 201
    assert len(await env.sources.list_active(DEV2)) == 1


async def test_account_of_x_never_creates_rows_of_y(client, env):
    await client.post(SOURCE_URL.format(ACCOUNT_1), content=body())
    assert await env.sources.list_active(DEV2) == []


async def test_21st_row_is_409_but_an_existing_one_still_updates(client, env):
    for i in range(20):
        server = f"00000000-0000-0000-0000-{i:012d}"
        assert (
            await client.post(SOURCE_URL.format(ACCOUNT_1), content=body(server=server))
        ).status_code == 201
    over = await client.post(
        SOURCE_URL.format(ACCOUNT_1), content=body(server=SERVER_A)
    )
    assert over.status_code == 409
    assert await env.sources.count_for_device(DEV1) == 20
    again = await client.post(
        SOURCE_URL.format(ACCOUNT_1),
        content=body(server="00000000-0000-0000-0000-000000000003"),
    )
    assert again.status_code == 201


async def test_row_pending_removal_is_not_cleared_by_the_callback(client, env):
    row = await env.sources.upsert(DEV1, SERVER_A, "Music", 7)
    await env.sources.mark_removal_pending(DEV1, row.source_id)
    response = await client.post(SOURCE_URL.format(ACCOUNT_1), content=body())
    assert response.status_code == 409
    assert (await env.sources.get_by_id(row.source_id)).removal_pending is True


async def test_declared_oversize_body_is_413_without_reading(client, env):
    response = await client.post(
        SOURCE_URL.format(ACCOUNT_1), content=body(name="x" * 5000)
    )
    assert response.status_code == 413
    assert await env.sources.count_for_device(DEV1) == 0


async def test_chunked_oversize_body_is_413(client, env):
    async def chunks():
        for _ in range(10):
            yield b"x" * 1000

    response = await client.post(SOURCE_URL.format(ACCOUNT_1), content=chunks())
    assert response.status_code == 413


# ---- DELETE source (AC-A7) ------------------------------------------------------


async def test_delete_flags_the_row_and_keeps_it(client, env):
    row = await env.sources.upsert(DEV1, SERVER_A, "Music", 7)
    response = await client.delete(f"{SOURCE_URL.format(ACCOUNT_1)}/{row.source_id}")
    assert response.status_code == 200 and response.content == b""
    stored = await env.sources.get_by_id(row.source_id)
    assert stored is not None and stored.removal_pending is True


async def test_delete_unknown_id_is_a_noop_200(client):
    assert (
        await client.delete(f"{SOURCE_URL.format(ACCOUNT_1)}/999")
    ).status_code == 200
    assert (
        await client.delete(f"{SOURCE_URL.format(ACCOUNT_1)}/abc")
    ).status_code == 200


async def test_delete_never_touches_another_devices_row(client, env):
    other = await env.sources.upsert(DEV2, SERVER_A, "Music", 7)
    await client.delete(f"{SOURCE_URL.format(ACCOUNT_1)}/{other.source_id}")
    assert (await env.sources.get_by_id(other.source_id)).removal_pending is False


async def test_delete_unknown_account_is_404(client):
    assert (await client.delete(f"{SOURCE_URL.format('nobody')}/1")).status_code == 404


# ---- /full with rows (AC-A8) ----------------------------------------------------


async def test_full_lists_per_server_sources_and_drops_the_generic_one(client, env):
    a = await env.sources.upsert(DEV1, SERVER_A, "Music", 7)
    b = await env.sources.upsert(DEV1, SERVER_B, "Other", 7)
    gone = await env.sources.upsert(
        DEV1, "00000000-0000-0000-0000-000000000009", "x", 7
    )
    await env.sources.mark_removal_pending(DEV1, gone.source_id)
    await env.sources.upsert(DEV2, "00000000-0000-0000-0000-000000000008", "y", 7)

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
    row = await env.sources.upsert(DEV1, SERVER_A, "Music", 7)
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
    row = await env.sources.upsert(DEV1, SERVER_A, "Music", 7)
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
    row = await env.sources.upsert(DEV1, SERVER_A, "Music", 7)
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
    row = await env.sources.upsert(DEV1, SERVER_A, "Music", 7)
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
    return await env.sources.upsert(DEV1, SERVER_A, "Music", 7)


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


async def test_new_routes_log_no_body_no_server_no_names(client, env, caplog):
    caplog.set_level(logging.DEBUG)
    payload = body(name=SECRET_NAME)
    created = await client.post(SOURCE_URL.format(ACCOUNT_1), content=payload)
    row_id = xml(created).findtext("sourceID")
    await client.post(SOURCE_URL.format(ACCOUNT_1), content=b"<broken")
    await client.delete(f"{SOURCE_URL.format(ACCOUNT_1)}/{row_id}")
    await client.post(SOURCE_URL.format(ACCOUNT_1), content=body(name="x" * 6000))

    at_info = "\n".join(
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.INFO and r.name.startswith("opencloudtouch")
    )
    assert at_info
    for forbidden in (SERVER_A, SECRET_NAME, "Kitchen Speaker", "http://", "<source"):
        assert forbidden not in at_info
