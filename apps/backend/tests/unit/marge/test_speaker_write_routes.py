"""Regression tests for the Marge calls a SoundTouch speaker makes on its own.

Request bodies are copied from a wire capture of a real speaker (firmware 27.0.6),
with ids and addresses replaced. The speaker only applies a rename or a preset
write after OCT answered 2xx, and drops presets whose ``<source>`` it does not know,
so each test pins one of those observed failures.
"""

import base64
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_marge_service
from opencloudtouch.main import app
from opencloudtouch.marge.service import MargeService
from opencloudtouch.marge.xml_builder import build_streaming_account_xml
from opencloudtouch.presets.models import Preset
from opencloudtouch.recents.models import RecentPlay

BASE = "/streaming/account/123/device/AABBCCDDEEFF"
STREAM = "https://stream.example.org/live/aac"


def _orion_location(stream_url: str = STREAM, name: str = "Example FM") -> str:
    data = json.dumps({"streamUrl": stream_url, "name": name, "imageUrl": ""})
    encoded = base64.b64encode(data.encode()).decode()
    return f"http://oct.local:7778/core02/svc-bmx-adapter-orion/prod/orion/station?data={encoded}"


RENAME_BODY = (
    '<?xml version="1.0" encoding="UTF-8" ?><device deviceid="AABBCCDDEEFF">'
    "<name>Workshop New</name><macaddress>AABBCCDDEEFF</macaddress></device>"
)


def _preset_body(slot: int = 3) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8" ?><preset buttonNumber="{slot}">'
        "<sourceid>11</sourceid><name>Example FM</name><username>Example FM</username>"
        f"<location>{_orion_location()}</location>"
        "<contentItemType>stationurl</contentItemType><containerArt></containerArt></preset>"
    )


def _stored_preset(device_id, slot, source_id, name, location):
    return Preset(
        device_id=device_id,
        preset_number=slot,
        station_uuid="u",
        station_name=name,
        station_url=STREAM,
        source="LOCAL_INTERNET_RADIO",
    )


@pytest.fixture
def marge():
    service = AsyncMock(spec=MargeService)
    service.rename_device.return_value = True
    service.store_preset.side_effect = _stored_preset
    app.dependency_overrides[get_marge_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_marge_service, None)


@pytest.fixture
def client():
    return TestClient(app)


class TestRenameDevice:
    def test_rename_is_taken_over_and_answered_200(self, client, marge):
        response = client.put(BASE, content=RENAME_BODY)

        assert response.status_code == 200
        marge.rename_device.assert_awaited_once_with("AABBCCDDEEFF", "Workshop New")
        root = ElementTree.fromstring(response.text)
        assert root.tag == "device"
        assert root.findtext("name") == "Workshop New"

    def test_unknown_device_is_404(self, client, marge):
        marge.rename_device.return_value = False
        assert client.put(BASE, content=RENAME_BODY).status_code == 404

    @pytest.mark.parametrize(
        "body",
        [
            "not xml",
            "<other/>",
            '<device deviceid="AABBCCDDEEFF"><name> </name></device>',
            '<device deviceid="OTHER"><name>x</name></device>',
        ],
    )
    def test_unusable_body_is_400(self, client, marge, body):
        assert client.put(BASE, content=body).status_code == 400
        marge.rename_device.assert_not_awaited()


class TestPresetWrite:
    def test_preset_put_is_stored_and_answered_with_the_entry(self, client, marge):
        response = client.put(f"{BASE}/preset/3", content=_preset_body())

        assert response.status_code == 200
        args = marge.store_preset.await_args.args
        assert args[:4] == ("AABBCCDDEEFF", 3, "11", "Example FM")
        assert "orion" in args[4]
        root = ElementTree.fromstring(response.text)
        assert root.tag == "preset"
        assert root.get("buttonNumber") == "3"
        assert root.find("source").get("id") == "11"

    @pytest.mark.parametrize("slot", [0, 7])
    def test_slot_out_of_range_is_400(self, client, marge, slot):
        response = client.put(f"{BASE}/preset/{slot}", content=_preset_body())
        assert response.status_code == 400
        marge.store_preset.assert_not_awaited()

    def test_unusable_body_is_400(self, client, marge):
        assert client.put(f"{BASE}/preset/3", content="<preset/>").status_code == 400

    def test_delete_removes_the_slot(self, client, marge):
        response = client.delete(f"{BASE}/preset/2")

        assert response.status_code == 200
        marge.delete_preset.assert_awaited_once_with("AABBCCDDEEFF", 2)

    def test_delete_does_not_write_a_forged_log_line(self, client, marge, caplog):
        """A device id with a line break must not start a second log line."""
        with caplog.at_level("INFO"):
            client.delete("/streaming/account/123/device/AABB%0AFORGED%20line/preset/2")

        logged_id = caplog.text.split("DELETE device ")[1].split(" slot")[0]
        assert "\n" not in logged_id
        assert logged_id == "AABB FORGED line"

    def test_delete_out_of_range_is_400(self, client, marge):
        assert client.delete(f"{BASE}/preset/9").status_code == 400
        marge.delete_preset.assert_not_awaited()


class TestRecentsRead:
    def test_recents_are_returned_as_xml(self, client, marge):
        marge.get_recents.return_value = [
            RecentPlay(
                device_id="AABBCCDDEEFF",
                source="TUNEIN",
                location="/v1/playback/station/s1",
                name="Station",
                played_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
                id=5,
            )
        ]

        response = client.get(f"{BASE}/recents")

        assert response.status_code == 200
        root = ElementTree.fromstring(response.text)
        assert root.tag == "recents"
        recent = root.find("recent")
        assert recent.get("id") == "5"
        assert recent.findtext("sourceid") == "25"

    def test_no_recents_is_an_empty_list(self, client, marge):
        marge.get_recents.return_value = []
        root = ElementTree.fromstring(client.get(f"{BASE}/recents").text)
        assert root.tag == "recents"


class TestFullAccountKeepsEverySpeakerPreset:
    """The speaker silently drops a preset without a known ``<source>`` in /full."""

    @pytest.mark.parametrize("source", ["INTERNET_RADIO", "LOCAL_INTERNET_RADIO", None])
    def test_preset_always_carries_a_source_element(self, source):
        preset = Preset(
            device_id="AABBCCDDEEFF",
            preset_number=1,
            station_uuid="u",
            station_name="Imported",
            station_url=STREAM,
            source=source,
        )

        account = build_streaming_account_xml("123", "AABBCCDDEEFF", [preset], [])

        entry = account.find("./devices/device/presets/preset")
        assert entry.get("buttonNumber") == "1"
        assert entry.find("source").get("id") == "11"


class TestMargeServiceWrites:
    @pytest.fixture
    def parts(self):
        preset_repo = MagicMock()
        preset_repo.get_preset = AsyncMock(return_value=None)
        preset_repo.set_preset = AsyncMock(side_effect=lambda preset: preset)
        preset_repo.clear_preset = AsyncMock(return_value=1)
        device_repo = MagicMock()
        device_repo.update_name = AsyncMock(return_value=True)
        service = MargeService(preset_repo, MagicMock(), device_repo)
        return service, preset_repo, device_repo

    @pytest.mark.asyncio
    async def test_orion_location_is_unwrapped_to_the_stream_url(self, parts):
        service, _, _ = parts

        stored = await service.store_preset(
            "AABBCCDDEEFF", 3, "11", "Example FM", _orion_location()
        )

        assert stored.station_url == STREAM
        assert stored.source == "LOCAL_INTERNET_RADIO"

    @pytest.mark.asyncio
    async def test_tunein_location_is_kept(self, parts):
        service, _, _ = parts

        stored = await service.store_preset(
            "AABBCCDDEEFF", 1, "25", "Station", "/v1/playback/station/s1"
        )

        assert (stored.source, stored.station_url) == (
            "TUNEIN",
            "/v1/playback/station/s1",
        )

    @pytest.mark.asyncio
    async def test_existing_slot_keeps_its_uuid(self, parts):
        service, preset_repo, _ = parts
        preset_repo.get_preset.return_value = Preset(
            device_id="AABBCCDDEEFF",
            preset_number=3,
            station_uuid="keep-me",
            station_name="Old",
            station_url="x",
        )

        stored = await service.store_preset(
            "AABBCCDDEEFF", 3, "11", "New", _orion_location()
        )

        assert stored.station_uuid == "keep-me"

    @pytest.mark.asyncio
    async def test_rename_and_delete_go_to_the_repositories(self, parts):
        service, preset_repo, device_repo = parts

        assert await service.rename_device("AABBCCDDEEFF", "New") is True
        device_repo.update_name.assert_awaited_once_with("AABBCCDDEEFF", "New")
        assert await service.delete_preset("AABBCCDDEEFF", 2) == 1
        preset_repo.clear_preset.assert_awaited_once_with("AABBCCDDEEFF", 2)
