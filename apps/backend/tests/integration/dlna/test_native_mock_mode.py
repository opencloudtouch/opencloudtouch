"""Mock mode: native enable lifecycle through the HTTP API (AC-B1..B3, B5, B11)."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from opencloudtouch.core.dependencies import get_dlna_native_service
from opencloudtouch.core.exception_handlers import register_exception_handlers
from opencloudtouch.devices.mock_client import MockDeviceClient
from opencloudtouch.dlna import native_routes
from opencloudtouch.dlna.mock import MOCK_UUID_SERVER, MockDlnaClient, MockDlnaDiscovery
from opencloudtouch.dlna.native_service import DlnaNativeService
from opencloudtouch.dlna.service import DlnaService
from opencloudtouch.marge.source_repository import MargeSourceRepository
from opencloudtouch.presets.models import Preset

DEV = "AABBCC112233"  # a mock device id
SID = MOCK_UUID_SERVER.id
BASE = f"/api/dlna/native/{DEV}/servers/{SID}"


class Devices:
    async def get_by_device_id(self, device_id):
        return (
            SimpleNamespace(device_id=device_id, ip="192.0.2.10")
            if device_id == DEV
            else None
        )


class Presets:
    def __init__(self):
        self.items: list[Preset] = []

    async def get_all_presets(self, device_id):
        return self.items

    async def set_preset(self, preset):
        return preset


@pytest.fixture
async def env(tmp_path):
    repo = MargeSourceRepository(tmp_path / "n.db")
    await repo.initialize()
    MockDeviceClient.reset_sources()

    async def listed(device_id):
        return [row.account for row in await repo.list_active(device_id)]

    MockDeviceClient.listed_accounts = listed
    presets = Presets()
    service = DlnaNativeService(
        repo,
        Devices(),
        DlnaService(MockDlnaDiscovery(), MockDlnaClient()),
        presets,
        client_factory=lambda device: MockDeviceClient(device.device_id),
        poll_interval=0.01,
    )
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(native_routes.router)
    app.dependency_overrides[get_dlna_native_service] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t"
    ) as http:
        yield http, presets, repo
    MockDeviceClient.reset_sources()
    await repo.close()


async def _state(client):
    servers = (await client.get(f"/api/dlna/native?device_id={DEV}")).json()["servers"]
    return next(s for s in servers if s["server_id"] == SID)


async def test_lifecycle_without_network(env):
    client, _, _ = env
    first = await _state(client)
    assert (first["state"], first["server_known"], first["source_id"]) == (
        "not_enabled",
        True,
        None,
    )

    put = await client.put(BASE)
    assert (put.status_code, put.json()) == (200, {"server_id": SID, "state": "ready"})
    assert MockDeviceClient.pair_calls == []  # up to date: no re-pairing
    assert (await _state(client))["source_id"] >= 20000000

    again = await client.put(BASE)
    assert (again.status_code, again.json()["state"]) == (200, "ready")

    assert (await client.get(f"{BASE}/presets")).json() == {"slots": []}
    assert (await client.delete(BASE)).json() == {"affected_slots": []}
    assert (await _state(client))["state"] == "not_enabled"


async def test_stale_speaker_is_re_paired_once(env):
    client, _, _ = env
    MockDeviceClient.stale_devices.add(DEV)
    put = await client.put(BASE)
    assert (put.status_code, put.json()["state"]) == (200, "ready")
    assert MockDeviceClient.pair_calls == [DEV]  # no marge account: device id


async def test_in_use_conflict_and_force(env):
    client, presets, _ = env
    (await client.put(BASE))
    presets.items.append(
        Preset(
            device_id=DEV,
            preset_number=3,
            station_uuid="dlna-x",
            station_name="Folder",
            station_url=f"dlna://{SID}/music",
            source="DLNA",
            native_type="dir",
        )
    )
    assert (await client.get(f"{BASE}/presets")).json() == {
        "slots": [{"preset_number": 3, "name": "Folder"}]
    }
    conflict = await client.delete(BASE)
    assert (conflict.status_code, conflict.json()["code"]) == (
        409,
        "dlna_native_in_use",
    )
    forced = await client.delete(f"{BASE}?force=true")
    assert (forced.status_code, forced.json()) == (200, {"affected_slots": [3]})
    assert presets.items[0].native_type is None


async def test_error_codes_and_check_order(env):
    client, _, _ = env
    unknown_device = await client.put(f"/api/dlna/native/NOPE/servers/{SID}")
    assert (unknown_device.status_code, unknown_device.json()["code"]) == (
        404,
        "device_not_found",
    )
    unknown_server = await client.put(f"/api/dlna/native/{DEV}/servers/nope")
    assert (unknown_server.status_code, unknown_server.json()["code"]) == (
        404,
        "dlna_server_not_found",
    )
    assert (await client.get("/api/dlna/native?device_id=NOPE")).status_code == 404


async def test_unbrowsable_server_is_unavailable(env):
    client, _, _ = env
    MockDeviceClient.unbrowsable_servers.add(SID.lower())
    put = await client.put(BASE)
    assert (put.status_code, put.json()["state"]) == (200, "unavailable")
    assert (await _state(client))["state"] == "unavailable"
