"""Tests for marge streaming-specific and auxiliary routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from xml.etree import ElementTree

import pytest

from opencloudtouch.marge.routes import (
    blacklist_check,
    get_sourceproviders,
    power_on,
    scmudc_reporting,
    set_marge_account,
    streaming_full_account,
    streaming_power_on,
    streaming_sourceproviders,
    streaming_token,
)
from opencloudtouch.marge.service import MargeService


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
    """Tests for /streaming/account/{account_id}/full (fixes #188)."""

    @pytest.mark.asyncio
    async def test_returns_200_with_empty_presets(self):
        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.get_full_account = AsyncMock(return_value=([], []))

        result = await streaming_full_account("3784726", mock_marge)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_device_mapping(self):
        """No device found for account UUID → empty presets, no crash."""
        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.resolve_device_id_for_account = AsyncMock(return_value=None)

        result = await streaming_full_account("9999999", mock_marge)
        assert result.status_code == 200
        root = ElementTree.fromstring(result.body.decode())
        assert root.findall(".//preset") == []

    @pytest.mark.asyncio
    async def test_media_type_is_bose_streaming(self):
        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.get_full_account = AsyncMock(return_value=([], []))

        result = await streaming_full_account("3784726", mock_marge)
        assert "bose.streaming" in result.media_type

    @pytest.mark.asyncio
    async def test_returns_bose_account_xml(self):
        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.resolve_device_id_for_account = AsyncMock(return_value="AABB")
        mock_marge.get_full_account = AsyncMock(return_value=([], []))

        result = await streaming_full_account("3784726", mock_marge)
        root = ElementTree.fromstring(result.body.decode())
        assert root.tag == "account"
        assert root.get("id") == "3784726"

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

        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.resolve_device_id_for_account = AsyncMock(return_value="AABB")
        mock_marge.get_full_account = AsyncMock(return_value=([mock_preset], []))

        result = await streaming_full_account("3784726", mock_marge)
        root = ElementTree.fromstring(result.body.decode())
        assert len(root.findall("./devices/device/presets/preset")) == 1

    @pytest.mark.asyncio
    async def test_includes_recents_in_response(self):
        """Streaming endpoint must include recents (not empty list)."""
        mock_recent = MagicMock()
        mock_recent.source = "TUNEIN"
        mock_recent.location = "/v1/playback/station/s33828"
        mock_recent.name = "WDR 2"
        mock_recent.id = 42
        mock_recent.played_at = datetime(2026, 3, 29, 21, 33, tzinfo=UTC)

        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.resolve_device_id_for_account = AsyncMock(return_value="AABB")
        mock_marge.get_full_account = AsyncMock(return_value=([], [mock_recent]))

        result = await streaming_full_account("3784726", mock_marge)
        root = ElementTree.fromstring(result.body.decode())
        recents = root.findall("./devices/device/recents/recent")
        assert len(recents) == 1
        assert recents[0].get("id") == "42"
        assert recents[0].findtext("lastplayedat") == "2026-03-29T21:33:00.000+00:00"
        assert recents[0].findtext("sourceid") == "25"


class TestScmudcReporting:
    @pytest.mark.asyncio
    async def test_returns_200(self):
        result = await scmudc_reporting("689E194F7D2F")
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_accepts_any_device_id(self):
        result = await scmudc_reporting("ANYTHING")
        assert result.status_code == 200


class TestStreamingToken:
    """Tests for /streaming/device/{device_id}/streaming_token (Issue #167)."""

    @pytest.mark.asyncio
    async def test_returns_200_json(self):
        result = await streaming_token("689E194F7D2F")
        assert result.status_code == 200
        assert result.media_type == "application/json"

    @pytest.mark.asyncio
    async def test_contains_access_token(self):
        import json

        result = await streaming_token("689E194F7D2F")
        body = json.loads(result.body.decode())
        assert "access_token" in body
        assert body["access_token"] == "opencloudtouch"

    @pytest.mark.asyncio
    async def test_contains_expires_in(self):
        import json

        result = await streaming_token("AABBCCDDEEFF")
        body = json.loads(result.body.decode())
        assert body["expires_in"] == 86400

    @pytest.mark.asyncio
    async def test_accepts_any_device_id(self):
        result = await streaming_token("ANYTHING")
        assert result.status_code == 200


class TestBlacklistCheck:
    """Tests for /v1/blacklist/{device_id} (Issue #167)."""

    @pytest.mark.asyncio
    async def test_get_returns_200_json(self):
        result = await blacklist_check("689E194F7D2F")
        assert result.status_code == 200
        assert result.media_type == "application/json"

    @pytest.mark.asyncio
    async def test_returns_not_blacklisted(self):
        import json

        result = await blacklist_check("689E194F7D2F")
        body = json.loads(result.body.decode())
        assert body["blacklisted"] is False
        assert body["items"] == []

    @pytest.mark.asyncio
    async def test_accepts_any_device_id(self):
        result = await blacklist_check("ANYTHING")
        assert result.status_code == 200


class TestSetMargeAccount:
    """Tests for /setMargeAccount (Issue #167 — margeAccountUUID)."""

    @pytest.mark.asyncio
    async def test_returns_200_xml(self):
        result = await set_marge_account()
        assert result.status_code == 200
        assert result.media_type == "application/xml"

    @pytest.mark.asyncio
    async def test_returns_status_xml(self):
        result = await set_marge_account()
        assert b"/setMargeAccount" in result.body


class TestAddRecent:
    """The speaker reports what it played via POST .../device/{id}/recent."""

    BODY = (
        "<recent><contentItemType>stationurl</contentItemType>"
        "<lastplayedat>2026-03-29T21:33:00+00:00</lastplayedat>"
        "<location>/v1/playback/station/s166521</location><name>SMOOTH JAZZ</name>"
        "<sourceid>25</sourceid></recent>"
    )
    URL = "/streaming/account/123/device/AABB/recent"

    @pytest.fixture
    def marge(self):
        from opencloudtouch.core.dependencies import get_marge_service
        from opencloudtouch.main import app

        service = AsyncMock(spec=MargeService)
        service.add_recent = AsyncMock(side_effect=lambda recent: _with_id(recent))
        app.dependency_overrides[get_marge_service] = lambda: service
        yield service
        app.dependency_overrides.pop(get_marge_service, None)

    def test_stores_recent_and_answers_201(self, marge):
        from fastapi.testclient import TestClient

        from opencloudtouch.main import app

        response = TestClient(app).post(self.URL, content=self.BODY)

        assert response.status_code == 201
        stored = marge.add_recent.await_args.args[0]
        assert (stored.device_id, stored.source, stored.name) == (
            "AABB",
            "TUNEIN",
            "SMOOTH JAZZ",
        )
        assert stored.location == "/v1/playback/station/s166521"
        root = ElementTree.fromstring(response.text)
        assert root.tag == "recent"
        assert root.get("id") == "7"
        assert root.findtext("sourceid") == "25"

    @pytest.mark.parametrize(
        "body", ["not xml", "<other/>", "<recent><name>x</name></recent>"]
    )
    def test_rejects_unusable_body(self, marge, body):
        from fastapi.testclient import TestClient

        from opencloudtouch.main import app

        assert TestClient(app).post(self.URL, content=body).status_code == 400
        marge.add_recent.assert_not_awaited()


def _with_id(recent):
    recent.id = 7
    return recent
