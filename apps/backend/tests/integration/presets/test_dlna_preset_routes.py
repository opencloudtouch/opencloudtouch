"""POST /api/presets/dlna against the fake media server and a fake speaker."""

import re
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from opencloudtouch.core.dlna_reference import DlnaReferenceTooLongError
from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.dlna.mock import MockDlnaClient, MockDlnaDiscovery
from opencloudtouch.dlna.service import DlnaService
from opencloudtouch.main import app
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService

SERVER = "mock-media-server"
BODY = {
    "device_id": "D",
    "preset_number": 1,
    "server_id": SERVER,
    "object_id": "music-001",
}


@pytest.fixture
async def speaker():
    client = AsyncMock()
    with (
        patch(
            "opencloudtouch.devices.repository.DeviceRepository.get_by_device_id",
            new=AsyncMock(return_value=MagicMock(ip="10.0.0.1")),
        ),
        patch("opencloudtouch.devices.adapter.get_device_client", return_value=client),
    ):
        yield client


@pytest.fixture
async def api(speaker):

    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "t.db")
        devices, presets = DeviceRepository(db), PresetRepository(db)
        await devices.initialize()
        await presets.initialize()
        app.state.preset_service = PresetService(presets, devices)
        app.state.dlna_service = DlnaService(MockDlnaDiscovery(), MockDlnaClient())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
        await presets.close()
        await devices.close()


@pytest.mark.asyncio
async def test_set_track_preset(api, speaker):
    r = await api.post("/api/presets/dlna", json=BODY)
    assert r.status_code == 201
    body = r.json()
    assert body["source"] == "DLNA"
    assert re.fullmatch(r"dlna-[0-9a-f]{16}", body["station_uuid"])
    assert body["station_url"].startswith("dlna://")
    assert body["station_name"] == "Track 001"
    assert body["dlna"] == {"server_id": SERVER, "object_id": "music-001"}

    xml = speaker.store_preset.await_args.kwargs
    assert xml["dlna_reference"].object_id == "music-001"

    listed = (await api.get("/api/presets/D")).json()
    assert listed[0]["dlna"] == body["dlna"]


@pytest.mark.asyncio
async def test_set_container_preset_skips_sub_folders(api):
    r = await api.post("/api/presets/dlna", json={**BODY, "object_id": "subfolders"})
    assert r.status_code == 201
    assert r.json()["station_name"] == "Many Folders"


@pytest.mark.asyncio
async def test_folder_without_audio_is_not_playable(api):
    r = await api.post("/api/presets/dlna", json={**BODY, "object_id": "albums"})
    assert r.status_code == 422
    assert r.json()["code"] == "dlna_not_playable"
    assert (await api.get("/api/presets/D")).json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("patch_body", "status", "code"),
    [
        ({"server_id": "nope"}, 404, "dlna_server_not_found"),
        ({"object_id": "nope"}, 404, "dlna_object_not_found"),
        ({"object_id": "mixed-image"}, 422, "dlna_not_playable"),
    ],
)
async def test_save_errors_are_coded(api, patch_body, status, code):
    r = await api.post("/api/presets/dlna", json={**BODY, **patch_body})
    assert (r.status_code, r.json()["code"]) == (status, code)


@pytest.mark.asyncio
async def test_extra_field_is_rejected(api, speaker):
    r = await api.post(
        "/api/presets/dlna", json={**BODY, "station_url": "http://evil/x.mp3"}
    )
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"
    speaker.store_preset.assert_not_awaited()


@pytest.mark.asyncio
async def test_object_id_over_512_is_a_validation_error(api):
    r = await api.post("/api/presets/dlna", json={**BODY, "object_id": "x" * 513})
    assert (r.status_code, r.json()["code"]) == (422, "validation_error")


@pytest.mark.asyncio
async def test_too_long_reference(api, speaker):
    speaker.store_preset.side_effect = DlnaReferenceTooLongError("too long")
    r = await api.post("/api/presets/dlna", json=BODY)
    assert (r.status_code, r.json()["code"]) == (422, "dlna_reference_too_long")
    assert (await api.get("/api/presets/D")).json() == []


@pytest.mark.asyncio
async def test_speaker_unreachable_saves_nothing(api, speaker):
    speaker.store_preset.side_effect = DeviceConnectionError("10.0.0.1", "down")
    r = await api.post("/api/presets/dlna", json=BODY)
    assert r.status_code == 503
    assert (await api.get("/api/presets/D")).json() == []


@pytest.mark.asyncio
async def test_unknown_device(api):
    with patch(
        "opencloudtouch.devices.repository.DeviceRepository.get_by_device_id",
        new=AsyncMock(return_value=None),
    ):
        r = await api.post("/api/presets/dlna", json=BODY)
    assert (r.status_code, r.json()["code"]) == (404, "device_not_found")
