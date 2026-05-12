"""Unit tests for marge account sync endpoints."""

from unittest.mock import AsyncMock, MagicMock
from xml.etree import ElementTree

import pytest

from opencloudtouch.marge.routes import (
    get_devices,
    get_full_account,
    get_presets,
    get_recents,
    get_sources,
)
from opencloudtouch.marge.service import MargeService


class TestMargeAccountEndpoints:
    """Unit tests for marge account endpoints."""

    @pytest.mark.asyncio
    async def test_get_full_account_empty(self):
        """Test full account sync with no presets/recents."""
        # Arrange
        device_id = "689E194F7D2F"
        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.get_full_account = AsyncMock(return_value=([], []))

        # Act
        result = await get_full_account(device_id, mock_marge)

        # Assert
        assert result.status_code == 200
        assert result.media_type == "application/xml"

        # Parse XML
        root = ElementTree.fromstring(result.body.decode())
        assert root.tag == "boseAccount"
        assert root.get("version") == "1.0"

        # Check presets empty
        presets = root.find("presets")
        assert presets is not None
        assert len(list(presets.findall("preset"))) == 0

    @pytest.mark.asyncio
    async def test_get_full_account_with_presets(self):
        """Test full account sync with presets."""
        # Arrange
        device_id = "689E194F7D2F"

        # Mock preset data
        mock_preset = MagicMock()
        mock_preset.slot = 1
        mock_preset.source = "TUNEIN"
        mock_preset.location = "/v1/playback/station/s33828"
        mock_preset.name = "WDR 2"
        mock_preset.image_url = "https://cdn-radiotime-logos.tunein.com/s33828q.png"
        mock_preset.created_at.timestamp.return_value = 1234567890
        mock_preset.updated_at.timestamp.return_value = 1234567890

        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.get_full_account = AsyncMock(return_value=([mock_preset], []))

        # Act
        result = await get_full_account(device_id, mock_marge)

        # Assert
        assert result.status_code == 200

        root = ElementTree.fromstring(result.body.decode())
        presets = root.find("presets")
        preset_list = list(presets.findall("preset"))
        assert len(preset_list) == 1

        preset = preset_list[0]
        assert preset.get("id") == "1"

        # Check ContentItem
        content_item = preset.find("ContentItem")
        assert content_item is not None
        assert content_item.get("source") == "TUNEIN"
        assert content_item.get("location") == "/v1/playback/station/s33828"

        item_name = content_item.find("itemName")
        assert item_name is not None
        assert item_name.text == "WDR 2"

    @pytest.mark.asyncio
    async def test_get_presets_endpoint(self):
        """Test presets-only endpoint."""
        # Arrange
        device_id = "689E194F7D2F"

        mock_preset = MagicMock()
        mock_preset.slot = 2
        mock_preset.source = "TUNEIN"
        mock_preset.location = "/v1/playback/station/s24896"
        mock_preset.name = "1LIVE"
        mock_preset.image_url = ""
        mock_preset.created_at.timestamp.return_value = 1234567890
        mock_preset.updated_at.timestamp.return_value = 1234567890

        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.get_presets = AsyncMock(return_value=[mock_preset])

        # Act
        result = await get_presets(device_id, mock_marge)

        # Assert
        assert result.status_code == 200
        root = ElementTree.fromstring(result.body.decode())
        assert root.tag == "presets"

        preset_list = list(root.findall("preset"))
        assert len(preset_list) == 1
        assert preset_list[0].get("id") == "2"

    @pytest.mark.asyncio
    async def test_get_recents_empty(self):
        """Test recents endpoint with no history."""
        # Arrange
        device_id = "689E194F7D2F"
        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.get_recents = AsyncMock(return_value=[])

        # Act
        result = await get_recents(device_id, mock_marge)

        # Assert
        assert result.status_code == 200
        root = ElementTree.fromstring(result.body.decode())
        assert root.tag == "recents"
        assert len(list(root.findall("recent"))) == 0

    @pytest.mark.asyncio
    async def test_get_sources(self):
        """Test sources endpoint."""
        # Arrange
        device_id = "689E194F7D2F"

        # Act
        result = await get_sources(device_id)

        # Assert
        assert result.status_code == 200
        root = ElementTree.fromstring(result.body.decode())
        assert root.tag == "sources"

        # Should have TUNEIN and BLUETOOTH at minimum
        sources = list(root.findall("source"))
        assert len(sources) >= 2

        tunein = next((s for s in sources if s.get("source") == "TUNEIN"), None)
        assert tunein is not None
        assert tunein.get("status") == "AVAILABLE"

    @pytest.mark.asyncio
    async def test_get_devices_empty(self):
        """Test devices endpoint (multiroom)."""
        # Arrange
        device_id = "689E194F7D2F"

        # Act
        result = await get_devices(device_id)

        # Assert
        assert result.status_code == 200
        root = ElementTree.fromstring(result.body.decode())
        assert root.tag == "devices"
        # Empty for now (no multiroom setup)
        assert len(list(root.findall("device"))) == 0


class TestMargeXMLBuilder:
    """Unit tests for XML building functions."""

    def test_build_preset_xml(self):
        """Test building preset XML from model."""
        from opencloudtouch.marge.xml_builder import build_preset_xml

        # Arrange
        mock_preset = MagicMock()
        mock_preset.slot = 1
        mock_preset.source = "TUNEIN"
        mock_preset.location = "/v1/playback/station/s33828"
        mock_preset.name = "Test Station"
        mock_preset.image_url = "https://example.com/logo.png"
        mock_preset.created_at.timestamp.return_value = 1234567890
        mock_preset.updated_at.timestamp.return_value = 1234567890

        # Act
        xml_elem = build_preset_xml(mock_preset)

        # Assert
        assert xml_elem.tag == "preset"
        assert xml_elem.get("id") == "1"

        content_item = xml_elem.find("ContentItem")
        assert content_item.get("source") == "TUNEIN"
        assert content_item.get("location") == "/v1/playback/station/s33828"

    def test_build_sources_xml(self):
        """Test building sources XML."""
        from opencloudtouch.marge.xml_builder import build_sources_xml

        # Act
        xml_elem = build_sources_xml()

        # Assert
        assert xml_elem.tag == "sources"
        sources = list(xml_elem.findall("source"))
        assert len(sources) > 0

        # Should have TUNEIN
        tunein = next((s for s in sources if s.get("source") == "TUNEIN"), None)
        assert tunein is not None


class TestMargeIntegration:
    """Integration tests with real preset repository."""

    @pytest.mark.asyncio
    async def test_full_account_with_db(self, test_db_path):
        """Test full account sync with real database."""
        from opencloudtouch.marge.routes import get_full_account
        from opencloudtouch.marge.service import MargeService
        from opencloudtouch.presets.repository import PresetRepository
        from opencloudtouch.recents.repository import RecentsRepository

        # Arrange
        preset_repo = PresetRepository(test_db_path)
        await preset_repo.initialize()
        recents_repo = RecentsRepository(test_db_path)
        await recents_repo.initialize()

        device_id = "TEST_DEVICE"
        marge = MargeService(preset_repo, recents_repo)

        try:
            # Act
            result = await get_full_account(device_id, marge)

            # Assert
            assert result.status_code == 200
            root = ElementTree.fromstring(result.body.decode())
            assert root.tag == "boseAccount"
        finally:
            await preset_repo.close()
            await recents_repo.close()


@pytest.fixture
def test_db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test_marge.db"
