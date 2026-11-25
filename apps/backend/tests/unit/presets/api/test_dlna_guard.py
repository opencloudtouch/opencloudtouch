"""Tests for the DLNA stream-URL guard and the speaker-first delete of DLNA presets."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.core.exceptions import CodedApiError, DeviceConnectionError
from opencloudtouch.presets.api.dlna_guard import reject_dlna_preset
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.service import PresetService


def _preset(source="STORED_MUSIC", account="uuid:abc/0") -> Preset:
    return Preset(
        device_id="D",
        preset_number=1,
        station_uuid="u",
        station_name="n",
        station_url="42",
        source=source,
        source_account=account,
    )


def test_guard_rejects_dlna_preset():
    with pytest.raises(CodedApiError) as exc:
        reject_dlna_preset(_preset())
    assert exc.value.status_code == 409
    assert exc.value.code == "dlna_preset_not_streamable"


def test_guard_allows_radio_preset():
    reject_dlna_preset(_preset(source="INTERNET_RADIO", account=None))


@pytest.fixture
def calls():
    """Shared recorder so the order of speaker and DB calls is visible."""
    return MagicMock()


@pytest.fixture
def service(calls):
    calls.db_clear = AsyncMock(return_value=1)
    repo = AsyncMock()
    repo.clear_preset = calls.db_clear
    device_repo = AsyncMock()
    device_repo.get_by_device_id = AsyncMock(return_value=MagicMock(ip="192.0.2.10"))
    return PresetService(repository=repo, device_repository=device_repo)


def _client(calls) -> AsyncMock:
    client = AsyncMock()
    client.remove_preset = calls.speaker_remove
    return client


@pytest.mark.asyncio
async def test_delete_dlna_preset_clears_speaker_first(service, calls):
    calls.speaker_remove = AsyncMock()
    with patch(
        "opencloudtouch.devices.adapter.get_device_client",
        return_value=_client(calls),
    ):
        assert await service.clear_preset("D", 1) is True

    assert [c[0] for c in calls.mock_calls] == ["speaker_remove", "db_clear"]


@pytest.mark.asyncio
async def test_delete_dlna_preset_speaker_failure_keeps_row(service, calls):
    calls.speaker_remove = AsyncMock(
        side_effect=DeviceConnectionError("192.0.2.10", "offline")
    )
    with patch(
        "opencloudtouch.devices.adapter.get_device_client",
        return_value=_client(calls),
    ):
        with pytest.raises(DeviceConnectionError):
            await service.clear_preset("D", 1)

    calls.db_clear.assert_not_awaited()
