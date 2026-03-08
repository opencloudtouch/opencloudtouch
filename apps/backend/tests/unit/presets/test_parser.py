"""Unit tests for DevicePresetParser.

Tests parse_presets() and parse_element() in isolation — no DB, no HTTP.
The parsing logic was extracted from PresetService for Single Responsibility.
"""

import base64
import json
from xml.etree import ElementTree as ET

import pytest

from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.parser import DevicePresetParser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_preset_xml(
    preset_id: str,
    source: str = "INTERNET_RADIO",
    location: str = "http://stream.example.com/live.mp3",
    item_name: str = "Test Station",
) -> ET.Element:
    """Build a single <preset> Element."""
    elem = ET.Element("preset", id=preset_id)
    ci = ET.SubElement(elem, "ContentItem", source=source, location=location)
    ET.SubElement(ci, "itemName").text = item_name
    return elem


def _build_presets_xml(*presets: dict) -> bytes:
    """Build a full <presets> document."""
    root = ET.Element("presets")
    for p in presets:
        child = ET.SubElement(root, "preset", id=str(p["id"]))
        ci = ET.SubElement(
            child,
            "ContentItem",
            source=p.get("source", "INTERNET_RADIO"),
            location=p.get("location", "http://stream.example.com/live.mp3"),
        )
        ET.SubElement(ci, "itemName").text = p.get("item_name", "Test")
    return ET.tostring(root)


def _bmx_location(stream_url: str, name: str = "BMX Station") -> str:
    """Build a BMX adapter URL with base64-encoded JSON payload."""
    payload = base64.b64encode(
        json.dumps({"streamUrl": stream_url, "name": name}).encode()
    ).decode()
    return f"http://content.api.bose.io:7777/core02/svc-bmx-adapter-orion/prod/orion/station?data={payload}"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def parser() -> DevicePresetParser:
    return DevicePresetParser()


# ---------------------------------------------------------------------------
# parse_presets — full XML document
# ---------------------------------------------------------------------------


class TestParsePresets:
    """Tests for parse_presets(device_id, xml_bytes)."""

    def test_empty_presets_element_returns_empty_list(self, parser):
        xml = ET.tostring(ET.Element("presets"))
        result = parser.parse_presets("dev-001", xml)
        assert result == []

    def test_single_internet_radio_preset(self, parser):
        xml = _build_presets_xml(
            {
                "id": 1,
                "source": "INTERNET_RADIO",
                "location": "http://radio.example.com/stream.mp3",
                "item_name": "My Radio",
            }
        )
        result = parser.parse_presets("dev-001", xml)

        assert len(result) == 1
        p = result[0]
        assert isinstance(p, Preset)
        assert p.device_id == "dev-001"
        assert p.preset_number == 1
        assert p.source == "INTERNET_RADIO"
        assert p.station_url == "http://radio.example.com/stream.mp3"
        assert p.station_name == "My Radio"

    def test_multiple_presets_all_returned(self, parser):
        xml = _build_presets_xml(
            {"id": 1, "source": "INTERNET_RADIO", "location": "http://a.com/s.mp3"},
            {"id": 2, "source": "TUNEIN", "location": "/v1/station/s1"},
            {"id": 3, "source": "INTERNET_RADIO", "location": "http://c.com/s.mp3"},
        )
        result = parser.parse_presets("dev-x", xml)
        assert len(result) == 3

    def test_invalid_presets_skipped_from_document(self, parser):
        """Out-of-range id (0) gets skipped, valid one (1) is returned."""
        xml = _build_presets_xml(
            {"id": 0, "source": "INTERNET_RADIO", "location": "http://a.com/s.mp3"},
            {"id": 1, "source": "INTERNET_RADIO", "location": "http://b.com/s.mp3"},
        )
        result = parser.parse_presets("dev-001", xml)
        assert len(result) == 1
        assert result[0].preset_number == 1


# ---------------------------------------------------------------------------
# parse_element — individual <preset> element
# ---------------------------------------------------------------------------


class TestParseElement:
    """Tests for parse_element(elem, device_id)."""

    def test_internet_radio_preset(self, parser):
        elem = _build_preset_xml("1", "INTERNET_RADIO", "http://r.com/s.mp3", "R")
        result = parser.parse_element(elem, "dev-001")

        assert result is not None
        assert result.source == "INTERNET_RADIO"
        assert result.station_uuid == "internet_radio_1"
        assert result.station_url == "http://r.com/s.mp3"
        assert result.station_name == "R"

    def test_tunein_preset(self, parser):
        elem = _build_preset_xml("3", "TUNEIN", "/v1/station/s12345", "TuneIn")
        result = parser.parse_element(elem, "dev-001")

        assert result is not None
        assert result.source == "TUNEIN"
        assert result.station_uuid == "tunein_/v1/station/s12345"
        assert result.preset_number == 3

    def test_local_internet_radio_oct_url(self, parser):
        location = "http://oct.local:7777/stations/preset/abc-uuid-123.mp3"
        elem = _build_preset_xml("4", "LOCAL_INTERNET_RADIO", location, "OCT Station")
        result = parser.parse_element(elem, "dev-001")

        assert result is not None
        assert result.source == "LOCAL_INTERNET_RADIO"
        assert result.station_uuid == "abc-uuid-123"
        assert result.station_url == location

    def test_local_internet_radio_bmx_url(self, parser):
        stream_url = "http://stream.example.com/live.mp3"
        location = _bmx_location(stream_url, "Bose Radio")
        elem = _build_preset_xml("2", "LOCAL_INTERNET_RADIO", location, "Old Name")
        result = parser.parse_element(elem, "dev-001")

        assert result is not None
        assert result.source == "INTERNET_RADIO"
        assert result.station_url == stream_url
        assert result.station_name == "Bose Radio"
        assert result.station_uuid.startswith("bmx_imported_2_")

    def test_unknown_source_imported_with_synthetic_uuid(self, parser):
        elem = _build_preset_xml("5", "SPOTIFY", "spotify:station:abc", "Spotify")
        result = parser.parse_element(elem, "dev-001")

        assert result is not None
        assert result.source == "SPOTIFY"
        assert result.station_uuid == "SPOTIFY_5"

    def test_missing_id_attribute_returns_none(self, parser):
        elem = ET.Element("preset")  # no id
        ci = ET.SubElement(
            elem, "ContentItem", source="INTERNET_RADIO", location="http://x.com"
        )
        ET.SubElement(ci, "itemName").text = "X"
        assert parser.parse_element(elem, "dev-001") is None

    def test_non_integer_id_returns_none(self, parser):
        elem = ET.Element("preset", id="abc")
        ci = ET.SubElement(
            elem, "ContentItem", source="INTERNET_RADIO", location="http://x.com"
        )
        ET.SubElement(ci, "itemName").text = "X"
        assert parser.parse_element(elem, "dev-001") is None

    def test_id_zero_returns_none(self, parser):
        elem = _build_preset_xml("0", "INTERNET_RADIO", "http://x.com/s.mp3")
        assert parser.parse_element(elem, "dev-001") is None

    def test_id_seven_returns_none(self, parser):
        elem = _build_preset_xml("7", "INTERNET_RADIO", "http://x.com/s.mp3")
        assert parser.parse_element(elem, "dev-001") is None

    def test_missing_content_item_returns_none(self, parser):
        elem = ET.Element("preset", id="1")  # no ContentItem
        assert parser.parse_element(elem, "dev-001") is None

    def test_missing_item_name_defaults_to_unknown(self, parser):
        elem = ET.Element("preset", id="1")
        ET.SubElement(
            elem, "ContentItem", source="INTERNET_RADIO", location="http://x.com"
        )  # no itemName child
        result = parser.parse_element(elem, "dev-001")

        assert result is not None
        assert result.station_name == "Unknown"


# ---------------------------------------------------------------------------
# BMX decoding edge cases
# ---------------------------------------------------------------------------


class TestBmxDecoding:
    """Edge cases for _decode_bmx_preset (via parse_element)."""

    def test_bmx_url_without_data_param_returns_none(self, parser):
        location = "http://content.api.bose.io:7777/core02/svc-bmx-adapter-orion/prod/orion/station"
        elem = _build_preset_xml("1", "LOCAL_INTERNET_RADIO", location)
        assert parser.parse_element(elem, "dev-001") is None

    def test_bmx_url_missing_stream_url_in_payload_returns_none(self, parser):
        payload = base64.b64encode(json.dumps({"name": "No URL"}).encode()).decode()
        location = f"http://content.api.bose.io:7777/orion/station?data={payload}"
        elem = _build_preset_xml("1", "LOCAL_INTERNET_RADIO", location)
        assert parser.parse_element(elem, "dev-001") is None

    def test_bmx_url_invalid_base64_returns_none(self, parser):
        location = "http://content.api.bose.io:7777/orion/station?data=!!!invalid!!!"
        elem = _build_preset_xml("1", "LOCAL_INTERNET_RADIO", location)
        assert parser.parse_element(elem, "dev-001") is None


# ---------------------------------------------------------------------------
# OCT URL decoding edge cases
# ---------------------------------------------------------------------------


class TestOctDecoding:
    """Edge cases for _decode_oct_preset (via parse_element)."""

    def test_oct_url_with_invalid_format_returns_none(self, parser):
        location = "http://unknown.host/something"
        elem = _build_preset_xml("1", "LOCAL_INTERNET_RADIO", location)
        assert parser.parse_element(elem, "dev-001") is None

    def test_oct_url_extracts_uuid_correctly(self, parser):
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        location = f"http://oct.local:7777/stations/preset/{uuid}.mp3"
        elem = _build_preset_xml("2", "LOCAL_INTERNET_RADIO", location)
        result = parser.parse_element(elem, "dev-001")

        assert result is not None
        assert result.station_uuid == uuid
