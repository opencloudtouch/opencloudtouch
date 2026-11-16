"""Mock mode: enable -> reboot -> save folder -> sync -> Marge XML (AC-C1, C3, C8, C9, C10, C11)."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from xml.etree import ElementTree as ET

import pytest
from httpx import ASGITransport, AsyncClient

from opencloudtouch.devices.mock_client import MockDeviceClient
from opencloudtouch.devices.repository import Device, DeviceRepository
from opencloudtouch.dlna.mock import MOCK_UUID_SERVER, MockDlnaClient, MockDlnaDiscovery
from opencloudtouch.dlna.native_service import DlnaNativeService
from opencloudtouch.dlna.service import DlnaService
from opencloudtouch.main import app
from opencloudtouch.marge.service import MargeService
from opencloudtouch.marge.source_repository import MargeSourceRepository
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService
from opencloudtouch.recents.repository import RecentsRepository

DEV = "AABBCC112233"  # a mock device id
SID = MOCK_UUID_SERVER.id
BODY = {"device_id": DEV, "preset_number": 3, "server_id": SID, "object_id": "music"}


@pytest.fixture
async def env():
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "t.db")
        devices, presets, recents = (
            DeviceRepository(db),
            PresetRepository(db),
            RecentsRepository(db),
        )
        sources = MargeSourceRepository(db)
        for repo in (devices, presets, recents, sources):
            await repo.initialize()
        await devices.upsert(Device(DEV, "192.0.2.10", "Speaker", "ST10", DEV, "1"))
        MockDeviceClient.reset_sources()

        async def on_register(device_id, server_id, name, provider_id):
            await sources.upsert(device_id, server_id, name, provider_id)

        MockDeviceClient.on_register = on_register
        dlna = DlnaService(MockDlnaDiscovery(), MockDlnaClient())
        native = DlnaNativeService(
            sources,
            devices,
            dlna,
            presets,
            client_factory=lambda d: MockDeviceClient(d.device_id),
            poll_interval=0.01,
        )
        preset_service = PresetService(presets, devices)
        preset_service.native_service = native
        app.state.preset_service = preset_service
        app.state.marge_service = MargeService(presets, recents, devices, sources)
        app.state.dlna_service = dlna
        app.state.dlna_native_service = native
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, preset_service, sources
        MockDeviceClient.on_register = None
        MockDeviceClient.reset_sources()
        for repo in (devices, presets, recents, sources):
            await repo.close()


def _speaker_xml(object_id: str, name: str) -> bytes:
    return (
        '<presets><preset id="3"><ContentItem source="STORED_MUSIC" type="dir" '
        f'location="{object_id}" sourceAccount="{SID}/0" isPresetable="true">'
        f"<itemName>{name}</itemName></ContentItem></preset></presets>"
    ).encode()


async def test_not_enabled_server_falls_back_to_v1(env):
    client, _, _ = env
    created = await client.post("/api/presets/dlna", json=BODY)
    assert created.status_code == 201, created.text
    assert created.json()["dlna_playback"] == "reference"
    assert created.json()["dlna"] == {"server_id": SID, "object_id": "music"}


async def test_enable_reboot_save_sync_and_marge(env, caplog):
    client, service, sources = env
    MockDeviceClient.provider_id = 50  # the speaker cached the old provider list
    put = await client.put(f"/api/dlna/native/{DEV}/servers/{SID}")
    assert (put.status_code, put.json()["state"]) == (202, "restart_required")
    await MockDeviceClient(DEV).reboot()

    with caplog.at_level(logging.DEBUG):
        created = await client.post("/api/presets/dlna", json=BODY)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["dlna_playback"] == "native"
    assert body["dlna"] == {"server_id": SID, "object_id": "music"}
    assert body["source"] == "DLNA"
    assert body["station_url"] == f"dlna://{SID}/music"
    own = "\n".join(
        r.getMessage() for r in caplog.records if r.name.startswith("opencloudtouch")
    )
    assert "Music" not in own and "mock-media.invalid" not in own  # AC-C11

    (listed,) = (await client.get(f"/api/presets/{DEV}")).json()
    assert listed["dlna_playback"] == "native"
    one = (await client.get(f"/api/presets/{DEV}/3")).json()
    assert one["dlna_playback"] == "native"

    row = await sources.get_by_server(DEV, SID)
    xml = (await client.get(f"/streaming/account/{DEV}/full")).text
    item = ET.fromstring(xml).find(".//preset[@buttonNumber='3']")
    assert item is not None
    assert item.findtext("location") == "music"
    assert item.findtext("contentItemType") == "dir"
    assert item.findtext("sourceid") == str(row.source_id)
    assert item.find("source") is not None and "orion" not in xml

    # The speaker reports the slot back through the Marge preset call (AC-C9).
    marge = app.state.marge_service
    await marge.store_preset(DEV, 3, str(row.source_id), "Music", "music", "dir", DEV)
    # ... and a sync of the speaker's own list keeps the slot unchanged.
    with patch.object(
        service,
        "_fetch_device_presets",
        AsyncMock(return_value=_speaker_xml("music", "Music")),
    ):
        assert (await client.post(f"/api/presets/{DEV}/sync")).status_code == 200
    (kept,) = (await client.get(f"/api/presets/{DEV}")).json()
    for key in ("station_uuid", "station_url", "source", "dlna", "dlna_playback"):
        assert kept[key] == body[key]


async def test_overwrite_with_radio_resets_native_type(env):
    client, service, _ = env
    await client.put(f"/api/dlna/native/{DEV}/servers/{SID}")
    await client.post("/api/presets/dlna", json=BODY)
    await service.repository.set_preset(
        Preset(
            DEV,
            3,
            "u",
            "Radio",
            "http://radio.example/s",
            source="LOCAL_INTERNET_RADIO",
        )
    )
    preset = await service.get_preset(DEV, 3)
    assert preset is not None and preset.native_type is None
    assert preset.to_dict()["dlna_playback"] is None
