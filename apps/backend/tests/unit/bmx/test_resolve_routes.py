"""Unit tests for BMX resolve endpoint.

Extracted from test_stubs.py (STORY-306): TestBmxResolve moved here
to co-locate tests with the module they test (resolve_routes.py).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.bmx.resolve_routes import resolve_router  # noqa: E402


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(resolve_router)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


class TestBmxResolve:
    """Tests for POST /bmx/resolve endpoint."""

    OCT_CONTENT_ITEM = (
        '<ContentItem source="INTERNET_RADIO" '
        'location="/oct/device/AABBCC112233/preset/1" '
        'isPresetable="true">'
        "<itemName>Absolut Relax</itemName>"
        "<stationName>Absolut Relax</stationName>"
        "</ContentItem>"
    )

    DIRECT_URL_CONTENT_ITEM = (
        '<ContentItem source="INTERNET_RADIO" '
        'location="http://stream.example.com/radio.mp3">'
        "<itemName>My Radio</itemName>"
        "</ContentItem>"
    )

    TUNEIN_CONTENT_ITEM = (
        '<ContentItem source="TUNEIN" '
        'location="/v1/playback/station/s123" '
        'stationId="s123">'
        "<itemName>TuneIn Station</itemName>"
        "</ContentItem>"
    )

    def test_oct_location_resolves_to_proxy_url(self, client, monkeypatch):
        """OCT /oct/device/{id}/preset/{N} locations are resolved to proxy URLs."""
        monkeypatch.setenv("OCT_BACKEND_URL", "http://192.168.1.50:7777")

        response = client.post(
            "/bmx/resolve",
            content=self.OCT_CONTENT_ITEM,
            headers={"Content-Type": "application/xml"},
        )

        assert response.status_code == 200
        content = response.text
        assert "192.168.1.50:7777/device/AABBCC112233/preset/1" in content
        assert 'source="INTERNET_RADIO"' in content
        assert 'type="stationurl"' in content

    def test_direct_http_url_passes_through(self, client):
        """Direct HTTP URLs are passed through unchanged."""
        response = client.post(
            "/bmx/resolve",
            content=self.DIRECT_URL_CONTENT_ITEM,
            headers={"Content-Type": "application/xml"},
        )

        assert response.status_code == 200
        assert "stream.example.com" in response.text

    def test_tunein_station_passes_through(self, client):
        """TuneIn stations with stationId are passed through (not supported yet)."""
        response = client.post(
            "/bmx/resolve",
            content=self.TUNEIN_CONTENT_ITEM,
            headers={"Content-Type": "application/xml"},
        )

        assert response.status_code == 200

    def test_unknown_source_passes_through(self, client):
        """Unknown source types are passed through."""
        content_item = (
            '<ContentItem source="SPOTIFY" location="spotify://track/123">'
            "<itemName>Song</itemName>"
            "</ContentItem>"
        )

        response = client.post(
            "/bmx/resolve",
            content=content_item,
            headers={"Content-Type": "application/xml"},
        )

        assert response.status_code == 200

    def test_oct_location_no_match_returns_400(self, client):
        """INTERNET_RADIO source with non-OCT, non-URL location returns 400."""
        content_item = (
            '<ContentItem source="INTERNET_RADIO" location="/unknown/path">'
            "<itemName>Station</itemName>"
            "</ContentItem>"
        )

        response = client.post(
            "/bmx/resolve",
            content=content_item,
            headers={"Content-Type": "application/xml"},
        )

        assert response.status_code == 400

    def test_oct_device_path_no_preset_segment_returns_400(self, client):
        """OCT path starting with /oct/device/ but missing /preset/{n} returns 400."""
        content_item = (
            '<ContentItem source="INTERNET_RADIO"'
            ' location="/oct/device/AABBCC/other/path">'
            "<itemName>Station</itemName>"
            "</ContentItem>"
        )

        response = client.post(
            "/bmx/resolve",
            content=content_item,
            headers={"Content-Type": "application/xml"},
        )

        assert response.status_code == 400

    def test_invalid_xml_returns_500(self, client):
        """Invalid XML body returns 500 error response."""
        response = client.post(
            "/bmx/resolve",
            content="not xml at all <<<",
            headers={"Content-Type": "application/xml"},
        )

        assert response.status_code == 500
