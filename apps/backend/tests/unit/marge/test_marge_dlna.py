"""DLNA presets in marge: XML builder (both entry points) and store call (AC-B13)."""

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest

from opencloudtouch.core.dlna_reference import (
    DlnaReference,
    build_orion_location,
    parse_orion_data,
    station_uuid,
    to_station_url,
)
from opencloudtouch.marge.service import MargeService
from opencloudtouch.marge.xml_builder import build_full_account_xml, build_presets_xml
from opencloudtouch.presets.models import Preset

REF = DlnaReference("udn-1", "a/b&c")


def _preset() -> Preset:
    return Preset(
        device_id="D",
        preset_number=2,
        station_uuid=station_uuid(REF),
        station_name="Song",
        station_url=to_station_url(REF),
        station_favicon="http://nas/c.jpg",
        source="DLNA",
    )


def _location(xml) -> str:
    return xml.find(".//ContentItem").get("location")


@pytest.mark.parametrize(
    "build", [build_presets_xml, lambda p: build_full_account_xml(p, [])]
)
def test_xml_carries_the_reference_not_a_stream_url(build):
    xml = build([_preset()])
    item = xml.find(".//ContentItem")
    assert item.get("source") == "LOCAL_INTERNET_RADIO"
    data = parse_qs(urlparse(item.get("location")).query)["data"][0]
    assert parse_orion_data(data) == (REF, "Song")
    assert "dlna://" not in item.get("location")
    assert xml.find(".//containerArt").text == "http://nas/c.jpg"


@pytest.fixture
def repo():
    repo = AsyncMock()
    repo.get_preset = AsyncMock(return_value=None)
    repo.set_preset = AsyncMock(side_effect=lambda p: p)
    return repo


@pytest.mark.asyncio
async def test_store_call_keeps_the_dlna_reference(repo):
    location = build_orion_location("http://oct:7777", REF, "Song")
    service = MargeService(repo, AsyncMock())
    saved = await service.store_preset("D", 2, "LOCAL_INTERNET_RADIO", "Song", location)
    assert saved.source == "DLNA"
    assert saved.station_uuid == station_uuid(REF)
    assert saved.station_url == to_station_url(REF)


@pytest.mark.asyncio
async def test_store_call_still_unwraps_radio_locations(repo):
    import base64
    import json

    data = base64.urlsafe_b64encode(
        json.dumps({"streamUrl": "http://r/s.mp3", "name": "R"}).encode()
    ).decode()
    location = f"http://oct/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
    saved = await MargeService(repo, AsyncMock()).store_preset(
        "D", 1, "LOCAL_INTERNET_RADIO", "R", location
    )
    assert (saved.source, saved.station_url) == (
        "LOCAL_INTERNET_RADIO",
        "http://r/s.mp3",
    )
