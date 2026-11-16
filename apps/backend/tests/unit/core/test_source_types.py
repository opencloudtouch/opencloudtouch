"""Pin test for the Marge source provider ids (AC-A1, AC-A2)."""

from opencloudtouch.core.source_types import (
    BASE_SOURCES,
    LEGACY_STREAMING_IDS,
    source_type_for_streaming_id,
)

COMMITTED_IDS = {
    "AIRPLAY": "42",
    "AUX": "41",
    "LOCAL_INTERNET_RADIO": "11",
    "QPLAY": "53",
    "SPOTIFY": "30",
    "STORED_MUSIC": "7",
    "STORED_MUSIC_MEDIA_RENDERER": "51",
    "TUNEIN": "25",
    "UPNP": "52",
}


def test_ids_equal_the_committed_table():
    assert {s.source_type: s.streaming_id for s in BASE_SOURCES} == COMMITTED_IDS


def test_legacy_id_is_an_input_alias_only():
    assert LEGACY_STREAMING_IDS == {"50": "STORED_MUSIC"}
    assert source_type_for_streaming_id("50") == "STORED_MUSIC"
    assert source_type_for_streaming_id("7") == "STORED_MUSIC"
    assert source_type_for_streaming_id("25") == "TUNEIN"
    assert source_type_for_streaming_id("20000001") is None
    assert "50" not in {s.streaming_id for s in BASE_SOURCES}
