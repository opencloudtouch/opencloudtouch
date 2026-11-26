"""Tests for marge/xml_builder.py — all branches including RadioBrowser presets."""

from unittest.mock import MagicMock
from xml.etree import ElementTree

import pytest

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


class TestBuildStreamingAccountXml:
    """The speaker rejects any other root than <account> ("account expected")."""

    def test_root_is_account_with_id(self):
        from opencloudtouch.marge.xml_builder import build_streaming_account_xml

        elem = build_streaming_account_xml("3784726")
        assert elem.tag == "account"
        assert elem.get("id") == "3784726"

    def test_has_required_account_children(self):
        from opencloudtouch.marge.xml_builder import build_streaming_account_xml

        elem = build_streaming_account_xml("1")
        assert elem.findtext("accountStatus") == "OK"
        assert elem.findtext("mode") == "global"
        assert elem.findtext("preferredLanguage") == "en"
        assert elem.find("devices") is not None
        assert elem.find("providerSettings") is not None

    def test_sources_carry_provider_and_name(self):
        from opencloudtouch.marge.xml_builder import build_streaming_account_xml

        sources = build_streaming_account_xml("1").findall("./sources/source")
        assert sources
        tunein = next(s for s in sources if s.findtext("sourcename") == "TUNEIN")
        assert tunein.get("id")
        assert tunein.findtext("sourceproviderid")
        assert tunein.find("createdOn") is not None
        assert tunein.find("updatedOn") is not None

    def test_device_carries_presets_in_account_shape(self):
        from opencloudtouch.marge.xml_builder import build_streaming_account_xml

        elem = build_streaming_account_xml("1", "AABB", [_soundtouch_preset(slot=3)])
        device = elem.find("./devices/device")
        assert device.get("deviceid") == "AABB"
        preset = device.find("./presets/preset")
        assert preset.get("buttonNumber") == "3"
        assert preset.findtext("location")
        assert preset.findtext("name")


def test_stored_music_source_element_shape():
    from datetime import UTC, datetime
    from xml.etree import ElementTree as ET

    from opencloudtouch.marge.source_repository import MediaServerSource
    from opencloudtouch.marge.xml_builder import stored_music_source_element

    now = datetime(2026, 11, 1, tzinfo=UTC)
    parent = ET.Element("sources")
    stored_music_source_element(
        parent, MediaServerSource(20000001, "acc", "udn-1", "NAS", now, now)
    )
    (source,) = parent
    assert (source.get("id"), source.get("type")) == ("20000001", "Audio")
    assert source.findtext("sourceproviderid") == "50"
    assert source.findtext("name") == source.findtext("username") == "udn-1/0"
    assert source.findtext("createdOn") == now.isoformat()


def test_stored_music_source_element_catalogue_id():
    from datetime import UTC, datetime
    from xml.etree import ElementTree as ET

    from opencloudtouch.marge.source_repository import MediaServerSource
    from opencloudtouch.marge.xml_builder import stored_music_source_element

    now = datetime(2026, 11, 1, tzinfo=UTC)
    parent = ET.Element("sources")
    stored_music_source_element(
        parent, MediaServerSource(20000001, "acc", "udn-1", "NAS", now, now), True
    )
    assert parent[0].findtext("sourceproviderid") == "7"


def _dlna_preset(slot: int = 5, location: str = "129901", name: str = "Album"):
    from datetime import UTC, datetime

    from opencloudtouch.presets.models import Preset

    now = datetime(2026, 11, 1, tzinfo=UTC)
    return Preset(
        device_id="AABB",
        preset_number=slot,
        station_uuid="",
        station_name=name,
        station_url=location,
        source="STORED_MUSIC",
        source_account="Udn-1/0",
        created_at=now,
        updated_at=now,
    )


def _stored(server_id: str = "Udn-1"):
    from datetime import UTC, datetime

    from opencloudtouch.marge.source_repository import MediaServerSource

    now = datetime(2026, 11, 1, tzinfo=UTC)
    return MediaServerSource(20000002, "acc", server_id, "NAS", now, now)


class TestNativeDlnaPreset:
    """A DLNA preset keeps its native ContentItem; an Orion URL broke the slot (T21 4i)."""

    @pytest.mark.parametrize(
        "location", ["129901", "130032 TRACK"], ids=["folder", "track"]
    )
    def test_preset_xml_is_native(self, location):
        ci = build_preset_xml(_dlna_preset(location=location)).find("ContentItem")
        assert ci.attrib == {
            "source": "STORED_MUSIC",
            "location": location,
            "sourceAccount": "Udn-1/0",
            "isPresetable": "true",
        }
        assert ci.findtext("itemName") == "Album"

    @pytest.mark.parametrize(
        ("catalogue_ids", "provider"), [(False, "50"), (True, "7")], ids=["v0", "v1"]
    )
    @pytest.mark.parametrize(
        "location", ["129901", "130032 TRACK"], ids=["folder", "track"]
    )
    def test_account_preset_references_stored_source(
        self, location, catalogue_ids, provider
    ):
        from opencloudtouch.marge.xml_builder import build_streaming_account_xml

        account = build_streaming_account_xml(
            "acc",
            "AABB",
            [_dlna_preset(location=location)],
            [],
            [_stored()],
            catalogue_ids,
        )
        preset = account.find("./devices/device/presets/preset")
        assert preset.get("buttonNumber") == "5"
        assert preset.findtext("location") == location
        assert preset.findtext("name") == "Album"
        assert preset.findtext("contentItemType") == ""
        assert "orion" not in ElementTree.tostring(preset, encoding="unicode")
        source = preset.find("source")
        assert source.get("id") == "20000002"
        assert source.findtext("username") == "Udn-1/0"
        assert source.findtext("sourceproviderid") == provider

    def test_account_preset_without_stored_source_stays_native(self):
        from opencloudtouch.marge.xml_builder import build_streaming_account_xml

        account = build_streaming_account_xml("acc", "AABB", [_dlna_preset()])
        preset = account.find("./devices/device/presets/preset")
        assert preset.findtext("location") == "129901"
        source = preset.find("source")
        assert source.findtext("sourcename") == "STORED_MUSIC"
        # The speaker keeps the account only if /full carries it (T22 5c).
        assert source.findtext("username") == "Udn-1/0"
        assert source.findtext("name") == "Udn-1/0"

    def test_radio_preset_unchanged_next_to_stored_sources(self):
        from opencloudtouch.marge.xml_builder import build_streaming_account_xml

        radio = _radiobrowser_preset()
        plain = build_streaming_account_xml("acc", "AABB", [radio])
        with_stored = build_streaming_account_xml(
            "acc", "AABB", [radio], [], [_stored()]
        )
        assert ElementTree.tostring(
            plain.find("./devices/device/presets/preset")
        ) == ElementTree.tostring(with_stored.find("./devices/device/presets/preset"))
