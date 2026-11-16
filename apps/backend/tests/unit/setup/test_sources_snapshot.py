"""Setup keeps the generic STORED_MUSIC source untouched (AC-A15)."""

from opencloudtouch.setup.persistence_service import (
    REQUIRED_SOURCE_TYPES,
    build_sources_xml,
)


def test_required_source_types_are_unchanged():
    assert REQUIRED_SOURCE_TYPES == {
        "AIRPLAY",
        "AUX",
        "LOCAL_INTERNET_RADIO",
        "QPLAY",
        "SPOTIFY",
        "STORED_MUSIC",
        "STORED_MUSIC_MEDIA_RENDERER",
        "TUNEIN",
        "UPNP",
    }


def test_sources_xml_keeps_the_generic_stored_music_key():
    xml = build_sources_xml()
    assert '<sourceKey type="STORED_MUSIC" account="" />' in xml
    assert "provider" not in xml.lower()
