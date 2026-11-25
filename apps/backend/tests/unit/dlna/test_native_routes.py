"""Tests for the per-speaker native media server routes."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core import error_codes
from opencloudtouch.core.dependencies import (
    get_dlna_native_service,
    get_dlna_service,
    get_speaker_migration_service,
)
from opencloudtouch.core.exception_handlers import register_exception_handlers
from opencloudtouch.core.exceptions import DeviceNotFoundError, raise_coded
from opencloudtouch.dlna.models import DlnaServer
from opencloudtouch.dlna.native_routes import router
from opencloudtouch.dlna.native_service import NativeState

UDN = "Aa000000-0000-4000-8000-0000000000Bb"
ORPHAN = "Cc000000-0000-4000-8000-0000000000Dd"
OTHER = "Ee000000-0000-4000-8000-0000000000Ff"


def _server(udn: str = UDN, name: str = "NAS", host: str = "192.0.2.20") -> DlnaServer:
    return DlnaServer(
        id=udn,
        name=name,
        location=f"http://{host}:8200/rootDesc.xml",
        control_url=f"http://{host}:8200/ctl/ContentDir",
    )


@pytest.fixture
def deps():
    native = AsyncMock()
    native.read_states.return_value = {}
    native.enable.return_value = NativeState.READY
    dlna = AsyncMock()
    dlna.get_servers.return_value = [_server()]
    migrations = AsyncMock()
    migrations.status.return_value = (0, None)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_dlna_native_service] = lambda: native
    app.dependency_overrides[get_dlna_service] = lambda: dlna
    app.dependency_overrides[get_speaker_migration_service] = lambda: migrations
    return TestClient(app), native, dlna, migrations


def test_list_unions_discovered_and_registered(deps):
    client, native, dlna, _ = deps
    dlna.get_servers.return_value = [_server(), _server(OTHER, "Other", "192.0.2.21")]
    native.read_states.return_value = {UDN.lower(): NativeState.READY}

    body = client.get("/api/dlna/native", params={"device_id": "device-a"}).json()

    assert body["migration_failed"] is False
    assert body["migration_reason"] is None
    assert [(s["server_id"], s["state"], s["discovered"]) for s in body["servers"]] == [
        (UDN, "ready", True),
        (OTHER, "not_enabled", True),
    ]
    native.read_states.assert_awaited_once_with("device-a")


def test_registered_not_found_is_listed_unavailable_and_removable(deps):
    client, native, _, _ = deps
    native.read_states.return_value = {ORPHAN: NativeState.UNAVAILABLE}

    body = client.get("/api/dlna/native", params={"device_id": "device-a"}).json()

    assert body["servers"][-1] == {
        "server_id": ORPHAN,
        "name": ORPHAN,
        "state": "unavailable",
        "discovered": False,
        "host": None,
    }
    response = client.delete(f"/api/dlna/native/device-a/servers/{ORPHAN}")
    assert response.status_code == 204
    native.remove.assert_awaited_once_with("device-a", ORPHAN, False)


def test_host_is_reported(deps):
    client, _, _, _ = deps

    body = client.get("/api/dlna/native", params={"device_id": "device-a"}).json()

    assert body["servers"][0]["host"] == "192.0.2.20"


def test_list_reports_migration_failure(deps):
    client, _, _, migrations = deps
    migrations.status.return_value = (0, "step 0->1 failed")

    body = client.get("/api/dlna/native", params={"device_id": "device-a"}).json()

    assert body["migration_failed"] is True
    assert body["migration_reason"] == "step 0->1 failed"


def test_states_are_read_live_each_request(deps):
    client, native, _, _ = deps
    native.read_states.side_effect = [
        {UDN: NativeState.READY},
        {UDN: NativeState.UNAVAILABLE},
    ]

    first = client.get("/api/dlna/native", params={"device_id": "device-a"}).json()
    second = client.get("/api/dlna/native", params={"device_id": "device-a"}).json()

    assert first["servers"][0]["state"] == "ready"
    assert second["servers"][0]["state"] == "unavailable"
    assert native.read_states.await_count == 2


def test_unknown_device_404(deps):
    client, native, _, _ = deps
    native.read_states.side_effect = DeviceNotFoundError("nope")

    response = client.get("/api/dlna/native", params={"device_id": "nope"})

    assert response.status_code == 404
    assert response.json()["code"] == error_codes.DEVICE_NOT_FOUND


def test_enable_returns_state(deps):
    client, native, _, _ = deps
    native.enable.return_value = NativeState.UNAVAILABLE

    response = client.put(f"/api/dlna/native/device-a/servers/{UDN.lower()}")

    assert response.status_code == 200
    assert response.json() == {
        "server_id": UDN,
        "name": "NAS",
        "state": "unavailable",
        "discovered": True,
        "host": "192.0.2.20",
    }
    native.enable.assert_awaited_once_with("device-a", UDN, "NAS")


def test_enable_registered_undiscovered_uses_its_id(deps):
    client, native, dlna, _ = deps
    dlna.get_servers.return_value = []
    native.read_states.return_value = {ORPHAN: NativeState.UNAVAILABLE}

    response = client.put(f"/api/dlna/native/device-a/servers/{ORPHAN.lower()}")

    assert response.json()["discovered"] is False
    native.enable.assert_awaited_once_with("device-a", ORPHAN, ORPHAN)


def test_enable_unknown_server_404_code(deps):
    client, native, _, _ = deps

    response = client.put(f"/api/dlna/native/device-a/servers/{OTHER}")

    assert response.status_code == 404
    assert response.json()["code"] == error_codes.DLNA_SERVER_NOT_FOUND
    native.enable.assert_not_awaited()


def test_enable_migration_failed_409(deps):
    client, native, _, _ = deps

    def refuse(*_args):
        raise_coded(
            409, error_codes.DLNA_MIGRATION_FAILED, "failed", extra={"reason": "x"}
        )

    native.enable.side_effect = refuse

    response = client.put(f"/api/dlna/native/device-a/servers/{UDN}")

    assert response.status_code == 409
    assert response.json()["code"] == error_codes.DLNA_MIGRATION_FAILED


def test_disable_409_code_and_slots(deps):
    client, native, _, _ = deps

    def refuse(*_args):
        raise_coded(
            409, error_codes.DLNA_NATIVE_SLOTS_AFFECTED, "used", extra={"slots": [3]}
        )

    native.remove.side_effect = refuse

    response = client.delete(f"/api/dlna/native/device-a/servers/{UDN}")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == error_codes.DLNA_NATIVE_SLOTS_AFFECTED
    assert body["extra"]["slots"] == [3]


def test_disable_204(deps):
    client, native, _, _ = deps

    response = client.delete(f"/api/dlna/native/device-a/servers/{UDN}")

    assert response.status_code == 204
    native.remove.assert_awaited_once_with("device-a", UDN, False)


def test_delete_force_param(deps):
    client, native, _, _ = deps

    response = client.delete(
        f"/api/dlna/native/device-a/servers/{UDN}", params={"force": "true"}
    )

    assert response.status_code == 204
    native.remove.assert_awaited_once_with("device-a", UDN, True)
