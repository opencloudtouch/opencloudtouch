"""Native STORED_MUSIC items in the speaker's /presets response (AC-A10)."""

from xml.etree import ElementTree as ET

from opencloudtouch.presets.parser import DevicePresetParser

SERVER = "11111111-2222-3333-4444-555555555555"


def _xml(*items: str) -> bytes:
    return f"<presets>{''.join(items)}</presets>".encode()


def _preset(slot, source, account, location="obj-7", ctype="dir"):
    return (
        f'<preset id="{slot}"><ContentItem source="{source}" type="{ctype}" '
        f'location="{location}" sourceAccount="{account}" isPresetable="true">'
        "<itemName>Album</itemName></ContentItem></preset>"
    )


def test_native_item_is_kept_as_a_dlna_preset():
    parsed = DevicePresetParser().parse_presets(
        "DEV", _xml(_preset(1, "STORED_MUSIC", f"{SERVER.upper()}/0"))
    )

    assert len(parsed) == 1
    p = parsed[0]
    assert p.source == "DLNA"
    assert p.station_url == f"dlna://{SERVER}/obj-7"
    assert p.station_uuid.startswith("dlna-")
    assert p.native_type == "dir"
    assert p.station_name == "Album"


def test_native_type_comes_from_the_content_item():
    parsed = DevicePresetParser().parse_presets(
        "DEV", _xml(_preset(1, "STORED_MUSIC", f"{SERVER}/0", ctype="track"))
    )
    assert parsed[0].native_type == "track"


def test_stored_music_without_matching_account_is_imported_as_before():
    parsed = DevicePresetParser().parse_presets(
        "DEV", _xml(_preset(1, "STORED_MUSIC", ""))
    )
    assert parsed[0].source == "STORED_MUSIC"
    assert parsed[0].native_type is None
    assert parsed[0].station_uuid == "STORED_MUSIC_1"


def test_parse_element_never_returns_none_for_a_native_item():
    element = ET.fromstring(_preset(3, "STORED_MUSIC", f"{SERVER}/0", location="x"))
    assert DevicePresetParser().parse_element(element, "DEV") is not None
