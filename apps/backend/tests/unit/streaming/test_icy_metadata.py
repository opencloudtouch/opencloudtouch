"""Tests for ICY metadata parser and probe.

Based on real-world samples collected from 15 radio stations
(see specs/008-metadata-stream/icy_samples.json).
"""

from __future__ import annotations

import pytest

from opencloudtouch.streaming.icy_metadata import (
    _decode_icy_bytes,
    _extract_stream_title,
    parse_stream_title,
)


class TestParseStreamTitle:
    """Tests for parse_stream_title — the core parser."""

    # --- Standard "Artist - Track" format ---

    def test_standard_artist_track(self):
        """'Artist - Track' → artist='Artist', track='Track'."""
        result = parse_stream_title("Free The Robots - Jazzhole")
        assert result.artist == "Free The Robots"
        assert result.track == "Jazzhole"

    def test_artist_track_with_extra_spaces(self):
        """'Kygo with Khalid  - Save my love' (double space before dash)."""
        result = parse_stream_title("Kygo with Khalid  - Save my love")
        assert result.artist == "Kygo with Khalid"
        assert result.track == "Save my love"

    def test_artist_track_with_parenthetical(self):
        """Track with mix/remix info in parentheses."""
        result = parse_stream_title("Siouxsie and the Banshees - Spellbound (12 mix)")
        assert result.artist == "Siouxsie and the Banshees"
        assert result.track == "Spellbound (12 mix)"

    def test_artist_track_preserves_raw(self):
        """raw_title always contains the original string."""
        result = parse_stream_title("  Artist - Track  ")
        assert result.raw_title == "  Artist - Track  "

    # --- "Track / Artist" format (SWR3 style) ---

    def test_slash_format_swaps_order(self):
        """'Save my love / Kygo with Khalid & Gryffin' → artist=right, track=left."""
        result = parse_stream_title("Save my love / Kygo with Khalid & Gryffin")
        assert result.artist == "Kygo with Khalid & Gryffin"
        assert result.track == "Save my love"

    # --- No separator (station name / show name) ---

    def test_no_separator_is_track_only(self):
        """'Die junge Nacht der ARD' → artist=None, track='...'."""
        result = parse_stream_title("Die junge Nacht der ARD")
        assert result.artist is None
        assert result.track == "Die junge Nacht der ARD"

    # --- Empty / whitespace ---

    def test_empty_string(self):
        result = parse_stream_title("")
        assert result.artist is None
        assert result.track is None

    def test_whitespace_only(self):
        result = parse_stream_title("   ")
        assert result.artist is None
        assert result.track is None

    # --- Station name echo filtering ---

    def test_station_name_echo_filtered(self):
        """Title == station_name → treated as no metadata."""
        result = parse_stream_title("Jazz Radio", station_name="Jazz Radio")
        assert result.artist is None
        assert result.track is None

    def test_station_name_echo_case_insensitive(self):
        result = parse_stream_title("JAZZ RADIO", station_name="Jazz Radio")
        assert result.artist is None
        assert result.track is None

    def test_station_name_no_false_positive(self):
        """Similar but different title should NOT be filtered."""
        result = parse_stream_title("Jazz Radio Live", station_name="Jazz Radio")
        assert result.track == "Jazz Radio Live"

    # --- Separator priority ---

    def test_dash_separator_takes_priority(self):
        """When both ' - ' and ' / ' exist, ' - ' wins (checked first)."""
        result = parse_stream_title("Artist - Track / Remix")
        assert result.artist == "Artist"
        assert result.track == "Track / Remix"

    # --- Edge cases ---

    def test_only_separator(self):
        """' - ' alone → both sides empty after strip → no separator match."""
        result = parse_stream_title(" - ")
        assert result.artist is None
        assert result.track == "-"

    def test_dummy_data_passes_through(self):
        """'9999999 - 9999999' — we don't filter dummy data (NRJ)."""
        result = parse_stream_title("9999999 - 9999999")
        assert result.artist == "9999999"
        assert result.track == "9999999"

    def test_frozen_dataclass(self):
        """IcyMetadata instances are immutable."""
        result = parse_stream_title("Artist - Track")
        with pytest.raises(AttributeError):
            result.artist = "changed"  # type: ignore[misc]


class TestExtractStreamTitle:
    """Tests for _extract_stream_title."""

    def test_standard_format(self):
        assert (
            _extract_stream_title("StreamTitle='Artist - Track';") == "Artist - Track"
        )

    def test_with_stream_url(self):
        meta = "StreamTitle='Artist - Track';StreamUrl='http://example.com';"
        assert _extract_stream_title(meta) == "Artist - Track"

    def test_empty_title(self):
        assert _extract_stream_title("StreamTitle='';") == ""

    def test_no_trailing_semicolon(self):
        """Some servers omit the trailing semicolon."""
        assert _extract_stream_title("StreamTitle='Artist - Track'") == "Artist - Track"

    def test_no_stream_title(self):
        assert _extract_stream_title("SomeOtherField='value';") is None

    def test_empty_string(self):
        assert _extract_stream_title("") is None

    def test_title_with_quotes_inside(self):
        """Titles with apostrophes (edge case)."""
        result = _extract_stream_title("StreamTitle='It's Alright';")
        assert result is not None


class TestDecodeIcyBytes:
    """Tests for _decode_icy_bytes."""

    def test_utf8(self):
        assert _decode_icy_bytes("Ünïcödé".encode("utf-8")) == "Ünïcödé"

    def test_latin1_fallback(self):
        """Latin-1 bytes that aren't valid UTF-8."""
        raw = bytes([0xC4, 0xD6, 0xDC])  # ÄÖÜ in Latin-1
        result = _decode_icy_bytes(raw)
        assert result == "ÄÖÜ"

    def test_null_padding_stripped(self):
        raw = b"Artist - Track\x00\x00\x00"
        assert _decode_icy_bytes(raw) == "Artist - Track"

    def test_empty_bytes(self):
        assert _decode_icy_bytes(b"") == ""

    def test_pure_null_bytes(self):
        assert _decode_icy_bytes(b"\x00\x00\x00") == ""
