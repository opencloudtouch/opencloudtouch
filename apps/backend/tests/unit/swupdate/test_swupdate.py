"""Unit tests for swupdate firmware index endpoints."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from opencloudtouch.swupdate.routes import _load_index_xml, router

app = FastAPI()
app.include_router(router)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# _load_index_xml (static file loader)
# ---------------------------------------------------------------------------


class TestLoadIndexXml:
    def test_returns_valid_xml_declaration(self):
        xml = _load_index_xml()
        assert xml.startswith('<?xml version="1.0"')

    def test_contains_index_root(self):
        xml = _load_index_xml()
        assert "<INDEX" in xml
        assert "</INDEX>" in xml

    def test_contains_soundtouch_20(self):
        xml = _load_index_xml()
        assert 'ID="0x0923"' in xml
        assert "SoundTouch 20" in xml

    def test_contains_soundtouch_30(self):
        xml = _load_index_xml()
        assert 'ID="0x0924"' in xml

    def test_contains_soundtouch_10(self):
        xml = _load_index_xml()
        assert 'ID="0x0939"' in xml
        assert "SoundTouch 10" in xml

    def test_contains_soundtouch_300(self):
        xml = _load_index_xml()
        assert 'ID="0x0949"' in xml
        assert "SoundTouch 300" in xml

    def test_contains_real_device_count(self):
        """Real Bose index has many more devices than the old synthetic one."""
        xml = _load_index_xml()
        assert xml.count("<DEVICE") >= 20

    def test_contains_real_firmware_revision(self):
        xml = _load_index_xml()
        assert 'REVISION="27.0.6.46330.5043500"' in xml

    def test_contains_real_crc(self):
        """Real index has actual CRC values, not 0x00000000."""
        xml = _load_index_xml()
        assert "0x2d5a971e" in xml

    def test_contains_downloads_bose_com(self):
        """Real index references downloads.bose.com for firmware files."""
        xml = _load_index_xml()
        assert "downloads.bose.com" in xml


# ---------------------------------------------------------------------------
# GET /updates/soundtouch
# ---------------------------------------------------------------------------


class TestFirmwareIndex:
    @pytest.mark.asyncio
    async def test_returns_200(self, client):
        resp = await client.get("/updates/soundtouch")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_xml_content_type(self, client):
        resp = await client.get("/updates/soundtouch")
        assert "xml" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_contains_index_element(self, client):
        resp = await client.get("/updates/soundtouch")
        assert "<INDEX" in resp.text
        assert "</INDEX>" in resp.text

    @pytest.mark.asyncio
    async def test_contains_device_entries(self, client):
        resp = await client.get("/updates/soundtouch")
        assert "<DEVICE" in resp.text

    @pytest.mark.asyncio
    async def test_contains_soundtouch_10_device(self, client):
        resp = await client.get("/updates/soundtouch")
        assert 'ID="0x0939"' in resp.text


# ---------------------------------------------------------------------------
# GET /ced/eup/downloads/rel/{filename} (legacy path)
# ---------------------------------------------------------------------------


class TestFirmwareDownloadLegacy:
    @pytest.mark.asyncio
    async def test_returns_404(self, client):
        resp = await client.get("/ced/eup/downloads/rel/SoundTouch_10.eup")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_xml_error(self, client):
        resp = await client.get("/ced/eup/downloads/rel/anything.eup")
        assert "xml" in resp.headers["content-type"]
        assert "<error>" in resp.text

    @pytest.mark.asyncio
    async def test_blocked_message(self, client):
        resp = await client.get("/ced/eup/downloads/rel/firmware.eup")
        assert "disabled" in resp.text.lower()


# ---------------------------------------------------------------------------
# GET /ced/soundtouch/downloads_stockholm/{path} (real Bose path)
# ---------------------------------------------------------------------------


class TestFirmwareDownloadReal:
    @pytest.mark.asyncio
    async def test_returns_404(self, client):
        resp = await client.get("/ced/soundtouch/downloads_stockholm/stu/s/Update.stu")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_blocked_message(self, client):
        resp = await client.get(
            "/ced/soundtouch/downloads_stockholm/stu/r/sm2/Update.stu"
        )
        assert "disabled" in resp.text.lower()
