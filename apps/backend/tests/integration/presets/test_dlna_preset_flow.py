"""Mock-mode flow: set -> list -> marge XML -> Orion press -> speaker sync (AC-B17)."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

import pytest
from httpx import ASGITransport, AsyncClient

from opencloudtouch.devices.repository import Device, DeviceRepository
from opencloudtouch.dlna.mock import MockDlnaClient, MockDlnaDiscovery
from opencloudtouch.dlna.service import DlnaService
from opencloudtouch.main import app
from opencloudtouch.marge.service import MargeService
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService
from opencloudtouch.recents.repository import RecentsRepository

ORION = "/core02/svc-bmx-adapter-orion/prod/orion/station"
DEVICE_ID = "DDEEFF445566"  # known to MockDeviceClient (OCT_MOCK_MODE)
BODY = {
    "device_id": DEVICE_ID,
    "preset_number": 3,
    "server_id": "mock-media-server",
    "object_id": "mixed-http",
}


@pytest.fixture
async def api():
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "t.db")
        devices, presets, recents = (
            DeviceRepository(db),
            PresetRepository(db),
            RecentsRepository(db),
        )
        for repo in (devices, presets, recents):
            await repo.initialize()
        await devices.upsert(
            Device(DEVICE_ID, "192.168.1.101", "Kitchen", "ST10", DEVICE_ID, "1")
        )
        dlna = DlnaService(MockDlnaDiscovery(), MockDlnaClient())
        dlna._servers["mock-media-server"] = (await dlna.get_servers())[0]
        app.state.preset_service = PresetService(presets, devices)
        app.state.marge_service = MargeService(presets, recents, devices)
        app.state.dlna_service = dlna
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, app.state.preset_service
        for repo in (devices, presets, recents):
            await repo.close()


@pytest.mark.asyncio
async def test_set_marge_press_and_sync(api):
    client, service = api
    created = await client.post("/api/presets/dlna", json=BODY)
    assert created.status_code == 201, created.text
    marker = created.json()["dlna"]

    xml = await client.get(f"/v1/systems/devices/{DEVICE_ID}/presets")
    location = ET.fromstring(xml.text).find(".//ContentItem").get("location")
    assert "dlna://" not in location

    press = await client.get(f"{ORION}?{urlparse(location).query}")
    assert press.status_code == 200
    assert press.json()["audio"]["streamUrl"].endswith("/media/mixed-http.mp3")
    assert press.json()["imageUrl"] == "http://mock-media.invalid/cover.jpg"

    speaker_xml = (
        f'<presets><preset id="3"><ContentItem source="LOCAL_INTERNET_RADIO" '
        f'type="stationurl" location="{location}"><itemName>x</itemName>'
        f"</ContentItem></preset></presets>"
    ).encode()
    with patch.object(
        service, "_fetch_device_presets", AsyncMock(return_value=speaker_xml)
    ):
        assert (await client.post(f"/api/presets/{DEVICE_ID}/sync")).status_code == 200
    (kept,) = (await client.get(f"/api/presets/{DEVICE_ID}")).json()
    assert kept["source"] == "DLNA" and kept["dlna"] == marker
    assert parse_qs(urlparse(location).query)["data"]
