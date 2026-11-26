"""Marge preset callback uses the shared ContentItem importer (decision 28)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_marge_service
from opencloudtouch.main import app
from opencloudtouch.marge.service import MargeService
from opencloudtouch.marge.source_repository import MediaServerSource
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.parser import preset_from_content_item

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _stored() -> MediaServerSource:
    return MediaServerSource(
        source_id=20000001,
        account_id="acc1",
        server_id="uuid-server-1",
        display_name="NAS",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _service(stored=None, existing=None):
    preset_repo = MagicMock()
    preset_repo.get_preset = AsyncMock(return_value=existing)
    preset_repo.set_preset = AsyncMock(side_effect=lambda preset: preset)
    device_repo = MagicMock()
    device_repo.get_by_device_id = AsyncMock(
        return_value=MagicMock(marge_account_uuid="acc1")
    )
    source_repo = MagicMock(get_by_id=AsyncMock(return_value=stored))
    return MargeService(preset_repo, MagicMock(), device_repo, source_repo)


@pytest.mark.asyncio
async def test_callback_uses_same_function():
    with patch(
        "opencloudtouch.marge.service.preset_from_content_item",
        wraps=preset_from_content_item,
    ) as spy:
        await _service(_stored()).store_preset("DEV1", 1, "20000001", "S", "1$4")
    spy.assert_called_once()


@pytest.mark.asyncio
async def test_callback_resolves_account_from_source_id():
    p = await _service(_stored()).store_preset("DEV1", 1, "20000001", "S", "1$4")
    assert (p.source, p.source_account) == ("STORED_MUSIC", "uuid-server-1/0")
    assert (p.station_uuid, p.station_url) == ("STORED_MUSIC_1", "1$4")


@pytest.mark.asyncio
async def test_callback_prefers_reported_account():
    p = await _service(_stored()).store_preset(
        "DEV1", 1, "20000001", "S", "1$4", "other/0"
    )
    assert p.source_account == "other/0"


@pytest.mark.asyncio
async def test_callback_without_account_or_source_row_no_dlna_marker():
    p = await _service(None).store_preset("DEV1", 1, "20000009", "S", "1$4")
    assert p.source_account is None and not p.is_dlna


@pytest.mark.asyncio
async def test_callback_keeps_cover_for_unchanged_location():
    existing = Preset(
        device_id="DEV1",
        preset_number=1,
        station_uuid="STORED_MUSIC_1",
        station_name="S",
        station_url="1$4",
        station_favicon="http://192.0.2.10/cover.jpg",
        source="STORED_MUSIC",
        source_account="uuid-server-1/0",
    )
    p = await _service(_stored(), existing).store_preset(
        "DEV1", 1, "20000001", "S", "1$4"
    )
    assert p.station_favicon == "http://192.0.2.10/cover.jpg"


def test_put_preset_passes_reported_source_account():
    marge = AsyncMock(spec=MargeService)
    marge.store_preset.return_value = Preset(
        device_id="DEV1",
        preset_number=2,
        station_uuid="STORED_MUSIC_2",
        station_name="Album",
        station_url="1$4",
        source="STORED_MUSIC",
        source_account="uuid-server-1/0",
    )
    app.dependency_overrides[get_marge_service] = lambda: marge
    try:
        body = (
            '<preset buttonNumber="2"><sourceid>20000001</sourceid>'
            "<name>Album</name><location>1$4</location>"
            "<sourceAccount>uuid-server-1/0</sourceAccount></preset>"
        )
        response = TestClient(app).put(
            "/streaming/account/acc1/device/DEV1/preset/2", content=body
        )
    finally:
        app.dependency_overrides.pop(get_marge_service, None)

    assert response.status_code == 200
    assert marge.store_preset.await_args.args == (
        "DEV1",
        2,
        "20000001",
        "Album",
        "1$4",
        "uuid-server-1/0",
    )
