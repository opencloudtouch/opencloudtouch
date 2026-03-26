"""Unit tests for BMX stream URL utilities."""

from opencloudtouch.bmx.stream_utils import convert_https_to_http


class TestConvertHttpsToHttp:
    """Tests for HTTPS → HTTP conversion (Bose device compatibility)."""

    def test_converts_https_to_http(self):
        assert (
            convert_https_to_http("https://stream.example.com/radio.mp3")
            == "http://stream.example.com/radio.mp3"
        )

    def test_leaves_http_unchanged(self):
        assert (
            convert_https_to_http("http://stream.example.com/radio.mp3")
            == "http://stream.example.com/radio.mp3"
        )

    def test_empty_string(self):
        assert convert_https_to_http("") == ""

    def test_preserves_path_and_query(self):
        url = "https://cdn.example.com/live/stream.mp3?token=abc123&format=mp3"
        expected = "http://cdn.example.com/live/stream.mp3?token=abc123&format=mp3"
        assert convert_https_to_http(url) == expected
