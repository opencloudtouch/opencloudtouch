"""Tests for marge/xml_builder.py — all branches including RadioBrowser presets."""

from unittest.mock import MagicMock

from opencloudtouch.marge.xml_builder import (
    build_devices_xml,
    build_full_account_xml,
    build_preset_xml,
    build_presets_xml,
    build_recents_xml,
    build_sources_xml,
)


def _soundtouch_preset(
    slot=1,
    source="TUNEIN",
    location="/v1/playback/station/s33828",
    name="Test Radio",
    image_url="https://example.com/logo.png",
):
    p = MagicMock()
    p.slot = slot
    p.source = source
    p.location = location
    p.name = name
    p.image_url = image_url
    p.created_at.timestamp.return_value = 1234567890
    p.updated_at.timestamp.return_value = 1234567891
    return p


def _radiobrowser_preset(
    preset_number=1,
    station_url="http://stream.example.com/radio",
    station_name="OCT Radio",
    station_favicon="https://example.com/fav.ico",
):
    """A RadioBrowser preset (no 'slot' attribute)."""
    p = MagicMock(spec=[])  # No attributes unless explicitly set
    p.preset_number = preset_number
    p.station_url = station_url
    p.station_name = station_name
    p.station_favicon = station_favicon
    p.created_at = MagicMock()
    p.created_at.timestamp.return_value = 1234567890
    p.updated_at = MagicMock()
    p.updated_at.timestamp.return_value = 1234567891
    return p


class TestBuildPresetXml:
    def test_soundtouch_preset_with_image(self):
        preset = _soundtouch_preset(slot=3)
        elem = build_preset_xml(preset)
        assert elem.tag == "preset"
        assert elem.get("id") == "3"
        ci = elem.find("ContentItem")
        assert ci is not None
        assert ci.get("source") == "TUNEIN"
        art = ci.find("containerArt")
        assert art is not None
        assert art.text == "https://example.com/logo.png"

    def test_soundtouch_preset_no_image(self):
        preset = _soundtouch_preset(image_url="")
        elem = build_preset_xml(preset)
        ci = elem.find("ContentItem")
        assert ci.find("containerArt") is None

    def test_radiobrowser_preset(self):
        """RadioBrowser preset uses preset_number and LOCAL_INTERNET_RADIO source."""
        preset = _radiobrowser_preset(preset_number=2)
        elem = build_preset_xml(preset)
        assert elem.tag == "preset"
        assert elem.get("id") == "2"
        ci = elem.find("ContentItem")
        assert ci is not None
        assert ci.get("source") == "LOCAL_INTERNET_RADIO"
        # Location must be Orion adapter URL, not raw stream URL
        location = ci.get("location")
        assert "core02/svc-bmx-adapter-orion/prod/orion/station" in location
        assert "data=" in location
        item_name = ci.find("itemName")
        assert item_name is not None
        assert item_name.text == "OCT Radio"

    def test_radiobrowser_preset_with_favicon(self):
        preset = _radiobrowser_preset(station_favicon="https://example.com/fav.ico")
        elem = build_preset_xml(preset)
        ci = elem.find("ContentItem")
        art = ci.find("containerArt")
        assert art is not None
        assert art.text == "https://example.com/fav.ico"

    def test_radiobrowser_preset_no_favicon(self):
        preset = _radiobrowser_preset(station_favicon=None)
        elem = build_preset_xml(preset)
        ci = elem.find("ContentItem")
        assert ci.find("containerArt") is None


class TestBuildPresetsXml:
    def test_empty_list(self):
        elem = build_presets_xml([])
        assert elem.tag == "presets"
        assert len(list(elem)) == 0

    def test_multiple_presets(self):
        presets = [_soundtouch_preset(slot=i) for i in range(1, 4)]
        elem = build_presets_xml(presets)
        assert len(elem.findall("preset")) == 3


class TestBuildRecentsXml:
    def test_empty_recents(self):
        elem = build_recents_xml()
        assert elem.tag == "recents"
        assert len(list(elem)) == 0

    def test_none_recents(self):
        elem = build_recents_xml(None)
        assert elem.tag == "recents"
        assert len(list(elem)) == 0

    def test_with_recents(self):
        recent = MagicMock()
        recent.source = "TUNEIN"
        recent.location = "/v1/playback/station/s33828"
        recent.name = "WDR 2"

        elem = build_recents_xml([recent])
        assert elem.tag == "recents"
        recent_elems = elem.findall("recent")
        assert len(recent_elems) == 1

        ci = recent_elems[0].find("ContentItem")
        assert ci is not None
        assert ci.get("source") == "TUNEIN"
        assert ci.get("location") == "/v1/playback/station/s33828"
        item_name = ci.find("itemName")
        assert item_name.text == "WDR 2"

    def test_with_multiple_recents(self):
        recents = []
        for i in range(3):
            r = MagicMock()
            r.source = "TUNEIN"
            r.location = f"/station/s{i}"
            r.name = f"Station {i}"
            recents.append(r)

        elem = build_recents_xml(recents)
        assert len(elem.findall("recent")) == 3


class TestBuildSourcesXml:
    def test_contains_standard_sources(self):
        elem = build_sources_xml()
        sources = elem.findall("source")
        source_names = [s.get("source") for s in sources]
        assert "TUNEIN" in source_names
        assert "AIRPLAY" in source_names
        assert "BLUETOOTH" not in source_names

    def test_all_available(self):
        elem = build_sources_xml()
        for s in elem.findall("source"):
            assert s.get("status") == "AVAILABLE"


class TestBuildDevicesXml:
    def test_empty_devices(self):
        elem = build_devices_xml()
        assert elem.tag == "devices"
        assert len(list(elem)) == 0

    def test_none_devices(self):
        elem = build_devices_xml(None)
        assert elem.tag == "devices"

    def test_with_devices(self):
        d1 = MagicMock()
        d1.device_id = "AABBCCDDEEFF"
        d1.name = "Living Room"
        d2 = MagicMock()
        d2.device_id = "112233445566"
        d2.name = "Bedroom"

        elem = build_devices_xml([d1, d2])
        device_elems = elem.findall("device")
        assert len(device_elems) == 2
        assert device_elems[0].get("deviceId") == "AABBCCDDEEFF"
        assert device_elems[1].get("name") == "Bedroom"


class TestBuildFullAccountXml:
    def test_structure(self):
        presets = [_soundtouch_preset(slot=1)]
        elem = build_full_account_xml(presets)
        assert elem.tag == "boseAccount"
        assert elem.get("version") == "1.0"
        assert elem.find("presets") is not None
        assert elem.find("recents") is not None
        assert elem.find("sources") is not None

    def test_with_recents(self):
        recent = MagicMock()
        recent.source = "TUNEIN"
        recent.location = "/station/s1"
        recent.name = "Radio 1"

        elem = build_full_account_xml([], [recent])
        recents = elem.find("recents")
        assert recents is not None
        assert len(recents.findall("recent")) == 1
