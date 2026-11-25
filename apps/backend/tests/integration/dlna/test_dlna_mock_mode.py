"""DLNA routes against the in-process mock media server (OCT_MOCK_MODE)."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from opencloudtouch.core.dependencies import (
    get_dlna_native_service,
    get_dlna_service,
    get_speaker_migration_service,
)
from opencloudtouch.core.exception_handlers import register_exception_handlers
from opencloudtouch.devices.mock_client import MockDeviceClient
from opencloudtouch.devices.repository import Device, DeviceRepository
from opencloudtouch.dlna.mock import MOCK_SERVER
from opencloudtouch.dlna.native_routes import router as native_router
from opencloudtouch.dlna.native_service import DlnaNativeService
from opencloudtouch.dlna.routes import router
from opencloudtouch.dlna.service import DlnaService
from opencloudtouch.marge.source_repository import MargeSourceRepository
from opencloudtouch.migrations.repository import SpeakerMigrationRepository
from opencloudtouch.migrations.service import SpeakerMigrationService

BASE = f"/api/dlna/servers/{MOCK_SERVER.id}"
DEVICE_ID = "AABBCC112233"


@pytest.fixture
async def client(monkeypatch, tmp_path):
    monkeypatch.setenv("OCT_MOCK_MODE", "true")
    monkeypatch.setattr(MockDeviceClient, "_MEDIA_SERVERS", {})
    db = tmp_path / "oct.db"
    device_repo = DeviceRepository(db)
    source_repo = MargeSourceRepository(db)
    migration_repo = SpeakerMigrationRepository(db)
    for repo in (device_repo, source_repo, migration_repo):
        await repo.initialize()
    try:
        # Mock speakers have no Marge account (their /info is never read over HTTP).
        await device_repo.upsert(
            Device(
                DEVICE_ID,
                "192.168.1.100",
                "Living Room",
                "SoundTouch 20",
                DEVICE_ID,
                "28",
            )
        )
        migrations = SpeakerMigrationService(migration_repo, device_repo)
        native = DlnaNativeService(
            source_repo, device_repo, migration_service=migrations
        )
        service = DlnaService()
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router)
        app.include_router(native_router)
        app.dependency_overrides[get_dlna_service] = lambda: service
        app.dependency_overrides[get_dlna_native_service] = lambda: native
        app.dependency_overrides[get_speaker_migration_service] = lambda: migrations
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as c:
            yield c
    finally:
        for repo in (device_repo, source_repo, migration_repo):
            await repo.close()


@pytest.mark.asyncio
async def test_browse_endpoint_in_mock_mode(client):
    assert [s["id"] for s in (await client.get("/api/dlna/servers")).json()] == [
        MOCK_SERVER.id
    ]
    resp = await client.get(f"{BASE}/browse", params={"object_id": "album-1"})
    assert resp.status_code == 200
    assert [i["id"] for i in resp.json()["items"]] == ["a1-t1", "a1-t2", "a1-t3"]


@pytest.mark.asyncio
async def test_album_root_in_mock_mode(client):
    resp = await client.get(f"{BASE}/album-root")
    assert resp.status_code == 200
    assert resp.json() == {"object_id": "albums"}
    path = await client.get(f"{BASE}/objects/path", params={"object_id": "a2-t3"})
    assert path.status_code == 200
    assert [p["object_id"] for p in path.json()["path"]] == ["albums", "album-2"]


@pytest.mark.asyncio
async def test_folder_with_image_first_is_not_audio_first(client):
    for container, expected in (("photos", False), ("album-1", True)):
        resp = await client.get(
            f"{BASE}/first-child-audio", params={"object_id": container}
        )
        assert resp.status_code == 200
        assert resp.json() == {"first_child_is_audio": expected}


@pytest.mark.asyncio
async def test_mock_server_reaches_ready_after_enable(client):
    def states(body):
        return [(s["server_id"], s["state"]) for s in body["servers"]]

    before = await client.get("/api/dlna/native", params={"device_id": DEVICE_ID})
    assert states(before.json()) == [(MOCK_SERVER.id, "not_enabled")]

    put = await client.put(f"/api/dlna/native/{DEVICE_ID}/servers/{MOCK_SERVER.id}")
    assert put.status_code == 200
    assert put.json()["state"] == "ready"

    after = await client.get("/api/dlna/native", params={"device_id": DEVICE_ID})
    assert states(after.json()) == [(MOCK_SERVER.id, "ready")]
