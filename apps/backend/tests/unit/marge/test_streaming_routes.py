"""Tests for marge streaming-specific and auxiliary routes."""

from unittest.mock import AsyncMock, MagicMock
from xml.etree import ElementTree

import pytest

from opencloudtouch.marge.routes import (
    get_sourceproviders,
    power_on,
    scmudc_reporting,
    streaming_full_account,
    streaming_power_on,
    streaming_sourceproviders,
)


class TestPowerOnEndpoint:
    @pytest.mark.asyncio
    async def test_power_on_post_returns_204(self):
        """POST power_on returns 204 No Content."""
        result = await power_on("689E194F7D2F")
        assert result.status_code == 204

    @pytest.mark.asyncio
    async def test_power_on_accepts_any_device_id(self):
        result = await power_on("AABBCCDDEEFF")
        assert result.status_code == 204


class TestGetSourceprovidersEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200_xml(self):
        result = await get_sourceproviders("689E194F7D2F")
        assert result.status_code == 200
        assert "xml" in result.media_type

    @pytest.mark.asyncio
    async def test_contains_tunein_provider(self):
        result = await get_sourceproviders("AABBCCDDEEFF")
        root = ElementTree.fromstring(result.body.decode())
        assert root.tag == "sourceproviders"
        providers = root.findall("sourceProvider")
        assert len(providers) >= 1
        names = [p.get("source") for p in providers]
        assert "TUNEIN" in names

    @pytest.mark.asyncio
    async def test_all_providers_available(self):
        result = await get_sourceproviders("689E194F7D2F")
        root = ElementTree.fromstring(result.body.decode())
        for src in root.findall("sourceProvider"):
            assert src.get("status") == "AVAILABLE"


class TestStreamingPowerOn:
    @pytest.mark.asyncio
    async def test_returns_200(self):
        result = await streaming_power_on()
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_media_type_is_bose_streaming(self):
        result = await streaming_power_on()
        assert "bose.streaming" in result.media_type


class TestStreamingSourceproviders:
    @pytest.mark.asyncio
    async def test_returns_200(self):
        result = await streaming_sourceproviders()
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_contains_tunein_provider(self):
        result = await streaming_sourceproviders()
        root = ElementTree.fromstring(result.body.decode())
        assert root.tag == "sourceProviders"
        providers = root.findall("sourceprovider")
        assert len(providers) >= 1
        names = [p.find("name").text for p in providers if p.find("name") is not None]
        assert "TUNEIN" in names

    @pytest.mark.asyncio
    async def test_tunein_has_correct_id(self):
        result = await streaming_sourceproviders()
        root = ElementTree.fromstring(result.body.decode())
        tunein = next(
            (
                p
                for p in root.findall("sourceprovider")
                if p.find("name") is not None and p.find("name").text == "TUNEIN"
            ),
            None,
        )
        assert tunein is not None
        assert tunein.get("id") == "25"

    @pytest.mark.asyncio
    async def test_media_type_is_bose_streaming(self):
        result = await streaming_sourceproviders()
        assert "bose.streaming" in result.media_type

    @pytest.mark.asyncio
    async def test_contains_local_internet_radio(self):
        result = await streaming_sourceproviders()
        root = ElementTree.fromstring(result.body.decode())
        names = [
            p.find("name").text
            for p in root.findall("sourceprovider")
            if p.find("name") is not None
        ]
        assert "LOCAL_INTERNET_RADIO" in names


class TestStreamingFullAccount:
    @pytest.mark.asyncio
    async def test_returns_200_with_empty_presets(self):
        mock_preset_repo = AsyncMock()
        mock_preset_repo.get_all_presets = AsyncMock(return_value=[])

        result = await streaming_full_account("3784726", mock_preset_repo)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_media_type_is_bose_streaming(self):
        mock_preset_repo = AsyncMock()
        mock_preset_repo.get_all_presets = AsyncMock(return_value=[])

        result = await streaming_full_account("3784726", mock_preset_repo)
        assert "bose.streaming" in result.media_type

    @pytest.mark.asyncio
    async def test_returns_bose_account_xml(self):
        mock_preset_repo = AsyncMock()
        mock_preset_repo.get_all_presets = AsyncMock(return_value=[])

        result = await streaming_full_account("3784726", mock_preset_repo)
        root = ElementTree.fromstring(result.body.decode())
        assert root.tag == "boseAccount"

    @pytest.mark.asyncio
    async def test_includes_presets_in_response(self):
        mock_preset = MagicMock()
        mock_preset.slot = 1
        mock_preset.source = "TUNEIN"
        mock_preset.location = "/v1/playback/station/s33828"
        mock_preset.name = "Radio NRW"
        mock_preset.image_url = ""
        mock_preset.created_at.timestamp.return_value = 1234567890
        mock_preset.updated_at.timestamp.return_value = 1234567890

        mock_preset_repo = AsyncMock()
        mock_preset_repo.get_all_presets = AsyncMock(return_value=[mock_preset])

        result = await streaming_full_account("3784726", mock_preset_repo)
        root = ElementTree.fromstring(result.body.decode())
        presets = root.find("presets")
        assert presets is not None
        assert len(presets.findall("preset")) == 1


class TestScmudcReporting:
    @pytest.mark.asyncio
    async def test_returns_200(self):
        result = await scmudc_reporting("689E194F7D2F")
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_accepts_any_device_id(self):
        result = await scmudc_reporting("ANYTHING")
        assert result.status_code == 200
