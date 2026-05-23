"""Tests for ICY metadata parser and probe.

Based on real-world samples collected from 15 radio stations
(see specs/008-metadata-stream/icy_samples.json).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from opencloudtouch.streaming.icy_metadata import (
    _decode_icy_bytes,
    _extract_stream_title,
    _parse_metadata_block,
    _read_icy_stream,
    parse_stream_title,
    probe_stream,
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


class TestParseMetadataBlock:
    """Tests for _parse_metadata_block."""

    def _build_metadata_buffer(self, title: str) -> bytearray:
        """Build a buffer with a properly encoded ICY metadata block."""
        meta_text = f"StreamTitle='{title}';".encode("utf-8")
        # Pad to multiple of 16
        padded_len = ((len(meta_text) + 15) // 16) * 16
        meta_padded = meta_text.ljust(padded_len, b"\x00")
        length_byte = padded_len // 16
        return bytearray([length_byte]) + bytearray(meta_padded)

    def test_empty_metadata_block(self):
        """Length byte 0 means empty metadata — skip."""
        buf = bytearray([0, 0xFF, 0xFF])  # length=0 + trailing data
        remaining, consumed, result = _parse_metadata_block(buf, None, None)
        assert consumed == 1
        assert result is None
        assert remaining == bytearray([0xFF, 0xFF])

    def test_valid_metadata_block(self):
        """Parse a complete metadata block with artist - track."""
        buf = self._build_metadata_buffer("Artist - Track")
        remaining, consumed, result = _parse_metadata_block(buf, None, None)
        assert result is not None
        assert result.artist == "Artist"
        assert result.track == "Track"
        assert consumed > 0

    def test_incomplete_block_needs_more_data(self):
        """Buffer too short for declared meta_length → return 0 consumed."""
        buf = bytearray([3])  # declares 48 bytes but only 1 byte available
        remaining, consumed, result = _parse_metadata_block(buf, None, None)
        assert consumed == 0
        assert result is None

    def test_with_logo_url(self):
        """icy_logo_url gets attached to result."""
        buf = self._build_metadata_buffer("Artist - Track")
        _, _, result = _parse_metadata_block(buf, None, "http://logo.png")
        assert result is not None
        assert result.station_logo_url == "http://logo.png"

    def test_without_logo_url(self):
        """No logo → station_logo_url stays None."""
        buf = self._build_metadata_buffer("Artist - Track")
        _, _, result = _parse_metadata_block(buf, None, None)
        assert result is not None
        assert result.station_logo_url is None

    def test_station_name_filtering(self):
        """Title matching station_name → metadata with None artist/track."""
        buf = self._build_metadata_buffer("Jazz Radio")
        _, _, result = _parse_metadata_block(buf, "Jazz Radio", None)
        assert result is not None
        assert result.artist is None
        assert result.track is None

    def test_no_stream_title_in_block(self):
        """Metadata block without StreamTitle field."""
        meta_text = b"StreamUrl='http://example.com';"
        padded_len = ((len(meta_text) + 15) // 16) * 16
        meta_padded = meta_text.ljust(padded_len, b"\x00")
        length_byte = padded_len // 16
        buf = bytearray([length_byte]) + bytearray(meta_padded)
        _, consumed, result = _parse_metadata_block(buf, None, None)
        assert result is None
        assert consumed > 0


class TestReadIcyStream:
    """Tests for _read_icy_stream."""

    @staticmethod
    def _mock_response(
        headers: dict[str, str],
        chunks: list[bytes],
    ) -> MagicMock:
        """Create a mock httpx.Response with async byte iteration."""
        response = MagicMock(spec=httpx.Response)
        response.headers = httpx.Headers(headers)

        async def aiter_bytes(chunk_size: int = 4096):
            for chunk in chunks:
                yield chunk

        response.aiter_bytes = aiter_bytes
        return response

    @pytest.mark.asyncio
    async def test_no_metaint_header(self):
        resp = self._mock_response({"content-type": "audio/mpeg"}, [])
        result = await _read_icy_stream(resp, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_metaint_value(self):
        resp = self._mock_response({"icy-metaint": "abc"}, [])
        result = await _read_icy_stream(resp, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_zero_metaint(self):
        resp = self._mock_response({"icy-metaint": "0"}, [])
        result = await _read_icy_stream(resp, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_negative_metaint(self):
        resp = self._mock_response({"icy-metaint": "-1"}, [])
        result = await _read_icy_stream(resp, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_extracts_metadata_from_stream(self):
        """Simulate a stream with metaint=16 and a metadata block."""
        metaint = 16
        audio_data = b"\x00" * metaint
        meta_text = b"StreamTitle='Foo - Bar';"
        padded_len = ((len(meta_text) + 15) // 16) * 16
        meta_padded = meta_text.ljust(padded_len, b"\x00")
        length_byte = bytes([padded_len // 16])

        chunk = audio_data + length_byte + meta_padded
        resp = self._mock_response(
            {"icy-metaint": str(metaint)},
            [chunk],
        )
        result = await _read_icy_stream(resp, None)
        assert result is not None
        assert result.artist == "Foo"
        assert result.track == "Bar"

    @pytest.mark.asyncio
    async def test_logo_from_icy_url_header(self):
        """icy-url header value lands in station_logo_url."""
        metaint = 8
        audio_data = b"\x00" * metaint
        meta_text = b"StreamTitle='A - B';"
        padded_len = ((len(meta_text) + 15) // 16) * 16
        meta_padded = meta_text.ljust(padded_len, b"\x00")
        length_byte = bytes([padded_len // 16])

        chunk = audio_data + length_byte + meta_padded
        resp = self._mock_response(
            {"icy-metaint": str(metaint), "icy-url": "http://logo.png"},
            [chunk],
        )
        result = await _read_icy_stream(resp, None)
        assert result is not None
        assert result.station_logo_url == "http://logo.png"

    @pytest.mark.asyncio
    async def test_empty_stream_returns_none(self):
        resp = self._mock_response({"icy-metaint": "16"}, [])
        result = await _read_icy_stream(resp, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_only_empty_metadata_blocks(self):
        """Stream with metadata length=0 (no metadata yet)."""
        metaint = 8
        audio_data = b"\x00" * metaint
        empty_meta = b"\x00"  # length byte = 0
        chunk = audio_data + empty_meta + audio_data + empty_meta
        resp = self._mock_response({"icy-metaint": str(metaint)}, [chunk])
        result = await _read_icy_stream(resp, None)
        assert result is None


class TestProbeStream:
    """Tests for probe_stream — integration-level with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_successful_probe(self):
        """probe_stream returns metadata from a mocked stream."""
        metaint = 16
        audio_data = b"\x00" * metaint
        meta_text = b"StreamTitle='Artist - Track';"
        padded_len = ((len(meta_text) + 15) // 16) * 16
        meta_padded = meta_text.ljust(padded_len, b"\x00")
        length_byte = bytes([padded_len // 16])
        chunk = audio_data + length_byte + meta_padded

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.headers = httpx.Headers({"icy-metaint": str(metaint)})

        async def aiter_bytes(chunk_size: int = 4096):
            yield chunk

        mock_response.aiter_bytes = aiter_bytes

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_client.stream.return_value = mock_stream_ctx

        mock_client_ctx = MagicMock()
        mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "opencloudtouch.streaming.icy_metadata.httpx.AsyncClient",
            return_value=mock_client_ctx,
        ):
            result = await probe_stream("http://stream.example.com/radio", timeout=2.0)

        assert result is not None
        assert result.artist == "Artist"
        assert result.track == "Track"

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        """Timeout during probe → returns None gracefully."""
        with patch(
            "opencloudtouch.streaming.icy_metadata.httpx.AsyncClient"
        ) as mock_cls:
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_ctx

            result = await probe_stream("http://stream.example.com/radio", timeout=0.1)
            assert result is None

    @pytest.mark.asyncio
    async def test_connect_error_returns_none(self):
        """Connection failure → returns None gracefully."""
        with patch(
            "opencloudtouch.streaming.icy_metadata.httpx.AsyncClient"
        ) as mock_cls:
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_ctx

            result = await probe_stream("http://stream.example.com/radio")
            assert result is None

    @pytest.mark.asyncio
    async def test_generic_error_returns_none(self):
        """Unexpected exception → returns None gracefully."""
        with patch(
            "opencloudtouch.streaming.icy_metadata.httpx.AsyncClient"
        ) as mock_cls:
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("unexpected"))
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_ctx

            result = await probe_stream("http://stream.example.com/radio")
            assert result is None
