"""Tests for PresetService business logic.

Covers sync_presets_from_device (all source branches),
set_preset, get_preset, get_all_presets, clear_preset, clear_all_presets.
"""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree import ElementTree as ET

import httpx
import pytest

from opencloudtouch.core.exceptions import DeviceNotFoundError
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.service import PresetService

# ---------------------------------------------------------------------------
# Helpers / XML builders
# ---------------------------------------------------------------------------


def _build_presets_xml(*presets: dict) -> bytes:
    """Build a <presets> XML document from a list of preset dicts.

    Each dict may contain: id, source, location, item_name
    """
    root = ET.Element("presets")
    for p in presets:
        preset_elem = ET.SubElement(root, "preset", id=str(p["id"]))
        ci = ET.SubElement(
            preset_elem,
            "ContentItem",
            source=p.get("source", "INTERNET_RADIO"),
            location=p.get("location", "http://stream.example.com/radio.mp3"),
        )
        item_name_elem = ET.SubElement(ci, "itemName")
        item_name_elem.text = p.get("item_name", "Test Station")
    return ET.tostring(root)


def _build_bmx_location(stream_url: str, name: str = "BMX Station") -> str:
    """Build a BMX adapter URL with base64-encoded JSON payload."""
    data = {"streamUrl": stream_url, "name": name}
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    return f"http://content.api.bose.io:7777/core02/svc-bmx-adapter-orion/prod/orion/station?data={encoded}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.set_preset = AsyncMock(side_effect=lambda p: p)
    repo.get_preset = AsyncMock(return_value=None)
    repo.get_all_presets = AsyncMock(return_value=[])
    repo.clear_preset = AsyncMock(return_value=1)
    repo.clear_all_presets = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_device_repo():
    repo = AsyncMock()
    device = MagicMock()
    device.ip = "192.168.1.100"
    device.device_id = "dev-001"
    repo.get_by_device_id = AsyncMock(return_value=device)
    return repo


@pytest.fixture
def service(mock_repo, mock_device_repo):
    return PresetService(repository=mock_repo, device_repository=mock_device_repo)


# ---------------------------------------------------------------------------
# sync_presets_from_device — device / HTTP errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_presets_raises_if_device_not_found(service, mock_device_repo):
    """Device not in DB → DeviceNotFoundError raised."""
    mock_device_repo.get_by_device_id = AsyncMock(return_value=None)

    with pytest.raises(DeviceNotFoundError, match="not found"):
        await service.sync_presets_from_device("unknown-device")


@pytest.mark.asyncio
async def test_sync_presets_raises_on_http_error(service):
    """Device HTTP request fails → httpx error propagates."""
    with patch("opencloudtouch.presets.service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client_cls.return_value = instance

        with pytest.raises(httpx.ConnectError):
            await service.sync_presets_from_device("dev-001")


# ---------------------------------------------------------------------------
# sync_presets_from_device — empty presets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_presets_empty_returns_zero(service):
    """No <preset> elements → 0 synced."""
    empty_xml = ET.tostring(ET.Element("presets"))
    with patch.object(
        service, "_fetch_device_presets", AsyncMock(return_value=empty_xml)
    ):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 0
    service.repository.set_preset.assert_not_called()


# ---------------------------------------------------------------------------
# sync_presets_from_device — INTERNET_RADIO source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_presets_internet_radio(service):
    xml = _build_presets_xml(
        {
            "id": 1,
            "source": "INTERNET_RADIO",
            "location": "http://radio.example.com/stream.mp3",
            "item_name": "My Radio",
        }
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 1
    saved: Preset = service.repository.set_preset.call_args[0][0]
    assert saved.source == "INTERNET_RADIO"
    assert saved.station_uuid == "internet_radio_1"
    assert saved.station_url == "http://radio.example.com/stream.mp3"
    assert saved.station_name == "My Radio"
    assert saved.device_id == "dev-001"
    assert saved.preset_number == 1


# ---------------------------------------------------------------------------
# sync_presets_from_device — TUNEIN source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_presets_tunein(service):
    xml = _build_presets_xml(
        {
            "id": 3,
            "source": "TUNEIN",
            "location": "/v1/playback/station/s12345",
            "item_name": "TuneIn Station",
        }
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 1
    saved: Preset = service.repository.set_preset.call_args[0][0]
    assert saved.source == "TUNEIN"
    assert saved.station_uuid == "tunein_/v1/playback/station/s12345"
    assert saved.station_url == "/v1/playback/station/s12345"
    assert saved.preset_number == 3


# ---------------------------------------------------------------------------
# sync_presets_from_device — LOCAL_INTERNET_RADIO — BMX URL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_presets_bmx_url_success(service):
    """BMX URL with valid base64 JSON → decoded and saved as INTERNET_RADIO."""
    stream_url = "http://stream.example.com/live.mp3"
    location = _build_bmx_location(stream_url, "Bose Radio")
    xml = _build_presets_xml(
        {
            "id": 2,
            "source": "LOCAL_INTERNET_RADIO",
            "location": location,
            "item_name": "Old Name",
        }
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 1
    saved: Preset = service.repository.set_preset.call_args[0][0]
    assert saved.source == "INTERNET_RADIO"
    assert saved.station_url == stream_url
    assert saved.station_name == "Bose Radio"
    assert saved.station_uuid.startswith("bmx_imported_2_")


@pytest.mark.asyncio
async def test_sync_presets_bmx_url_no_data_param(service):
    """BMX URL without ?data= → preset skipped."""
    location = "http://content.api.bose.io:7777/core02/svc-bmx-adapter-orion/prod/orion/station"
    xml = _build_presets_xml(
        {"id": 1, "source": "LOCAL_INTERNET_RADIO", "location": location}
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 0


@pytest.mark.asyncio
async def test_sync_presets_bmx_url_missing_stream_url(service):
    """BMX URL JSON without streamUrl → preset skipped."""
    data = {"name": "Station Without URL"}
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    location = f"http://content.api.bose.io:7777/orion/station?data={encoded}"
    xml = _build_presets_xml(
        {"id": 1, "source": "LOCAL_INTERNET_RADIO", "location": location}
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 0


@pytest.mark.asyncio
async def test_sync_presets_bmx_url_invalid_base64(service):
    """BMX URL with corrupted base64 → preset skipped (no exception raised)."""
    location = (
        "http://content.api.bose.io:7777/orion/station?data=!!!not_valid_base64!!!"
    )
    xml = _build_presets_xml(
        {"id": 1, "source": "LOCAL_INTERNET_RADIO", "location": location}
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 0


# ---------------------------------------------------------------------------
# sync_presets_from_device — LOCAL_INTERNET_RADIO — OCT URL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_presets_oct_url_success(service):
    """OCT descriptor URL → UUID extracted from path."""
    location = "http://oct.local:7777/stations/preset/abc-uuid-123.mp3"
    xml = _build_presets_xml(
        {
            "id": 4,
            "source": "LOCAL_INTERNET_RADIO",
            "location": location,
            "item_name": "My OCT Station",
        }
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 1
    saved: Preset = service.repository.set_preset.call_args[0][0]
    assert saved.source == "LOCAL_INTERNET_RADIO"
    assert saved.station_uuid == "abc-uuid-123"
    assert saved.station_url == location
    assert saved.preset_number == 4


@pytest.mark.asyncio
async def test_sync_presets_oct_url_invalid_location(service):
    """OCT local preset with unrecognized URL format → preset skipped."""
    xml = _build_presets_xml(
        {
            "id": 1,
            "source": "LOCAL_INTERNET_RADIO",
            "location": "http://unknown.host/something",
        }
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 0


# ---------------------------------------------------------------------------
# sync_presets_from_device — unknown source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_presets_unknown_source(service):
    """Unknown source type → imported with synthetic UUID, original source kept."""
    xml = _build_presets_xml(
        {
            "id": 5,
            "source": "SPOTIFY",
            "location": "spotify:station:abc",
            "item_name": "Spotify Station",
        }
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 1
    saved: Preset = service.repository.set_preset.call_args[0][0]
    assert saved.source == "SPOTIFY"
    assert saved.station_uuid == "SPOTIFY_5"


# ---------------------------------------------------------------------------
# sync_presets_from_device — preset validation (skipped cases)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_presets_skips_out_of_range_ids(service):
    """Preset IDs 0 and 7 are out of range and must be skipped."""
    xml = _build_presets_xml(
        {"id": 0, "source": "INTERNET_RADIO", "location": "http://x.com/s.mp3"},
        {"id": 7, "source": "INTERNET_RADIO", "location": "http://x.com/s.mp3"},
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 0


@pytest.mark.asyncio
async def test_sync_presets_skips_non_integer_ids(service):
    """Non-integer preset id → skipped."""
    root = ET.Element("presets")
    elem = ET.SubElement(root, "preset", id="abc")
    ci = ET.SubElement(
        elem, "ContentItem", source="INTERNET_RADIO", location="http://x.com"
    )
    ET.SubElement(ci, "itemName").text = "X"

    with patch.object(
        service, "_fetch_device_presets", AsyncMock(return_value=ET.tostring(root))
    ):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 0


@pytest.mark.asyncio
async def test_sync_presets_skips_missing_content_item(service):
    """Preset element without <ContentItem> is skipped."""
    root = ET.Element("presets")
    ET.SubElement(root, "preset", id="1")  # no ContentItem

    with patch.object(
        service, "_fetch_device_presets", AsyncMock(return_value=ET.tostring(root))
    ):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 0


@pytest.mark.asyncio
async def test_sync_presets_skips_missing_id_attribute(service):
    """Preset element without id attribute is skipped."""
    root = ET.Element("presets")
    ET.SubElement(root, "preset")  # no id

    with patch.object(
        service, "_fetch_device_presets", AsyncMock(return_value=ET.tostring(root))
    ):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 0


@pytest.mark.asyncio
async def test_sync_presets_multiple_presets(service):
    """Multiple valid presets → all saved, correct count returned."""
    xml = _build_presets_xml(
        {
            "id": 1,
            "source": "INTERNET_RADIO",
            "location": "http://a.com/s.mp3",
            "item_name": "A",
        },
        {"id": 2, "source": "TUNEIN", "location": "/v1/station/s999", "item_name": "B"},
        {
            "id": 3,
            "source": "INTERNET_RADIO",
            "location": "http://c.com/s.mp3",
            "item_name": "C",
        },
    )
    with patch.object(service, "_fetch_device_presets", AsyncMock(return_value=xml)):
        count = await service.sync_presets_from_device("dev-001")

    assert count == 3
    assert service.repository.set_preset.call_count == 3


# ---------------------------------------------------------------------------
# _fetch_device_presets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_device_presets_returns_content(service):
    """_fetch_device_presets returns response bytes on success."""
    expected = b"<presets/>"
    mock_response = MagicMock()
    mock_response.content = expected
    mock_response.raise_for_status = MagicMock()

    with patch("opencloudtouch.presets.service.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = instance

        result = await service._fetch_device_presets("192.168.1.100")

    assert result == expected
    instance.get.assert_called_once_with("http://192.168.1.100:8090/presets")


# ---------------------------------------------------------------------------
# set_preset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_preset_saves_to_database(service, mock_device_repo):
    """set_preset saves preset to DB and returns it."""
    saved_preset = MagicMock()
    service.repository.set_preset = AsyncMock(return_value=saved_preset)

    with patch("opencloudtouch.presets.service.httpx.AsyncClient"):
        with patch(
            "opencloudtouch.devices.adapter.get_device_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.store_preset = AsyncMock()
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            result = await service.set_preset(
                device_id="dev-001",
                preset_number=1,
                station_uuid="station-abc",
                station_name="Test FM",
                station_url="http://test.fm/stream.mp3",
            )

    assert result == saved_preset
    service.repository.set_preset.assert_called_once()
    called_preset: Preset = service.repository.set_preset.call_args[0][0]
    assert called_preset.device_id == "dev-001"
    assert called_preset.preset_number == 1
    assert called_preset.station_uuid == "station-abc"
    assert called_preset.source == "LOCAL_INTERNET_RADIO"


@pytest.mark.asyncio
async def test_set_preset_device_programming_failure_does_not_reraise(
    service, mock_device_repo
):
    """If Bose device programming fails, DB record is still returned."""
    saved_preset = MagicMock()
    service.repository.set_preset = AsyncMock(return_value=saved_preset)

    with patch("opencloudtouch.devices.adapter.get_device_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.store_preset = AsyncMock(
            side_effect=Exception("Device unreachable")
        )
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        result = await service.set_preset(
            device_id="dev-001",
            preset_number=2,
            station_uuid="uuid-xyz",
            station_name="Fails Station",
            station_url="http://fails.station/stream.mp3",
        )

    # Must NOT raise — failure is logged and swallowed
    assert result == saved_preset


@pytest.mark.asyncio
async def test_set_preset_device_not_found_during_programming(
    service, mock_device_repo
):
    """If device is missing when programming, a warning is logged but preset is returned."""
    mock_device_repo.get_by_device_id = AsyncMock(return_value=None)
    saved_preset = MagicMock()
    service.repository.set_preset = AsyncMock(return_value=saved_preset)

    result = await service.set_preset(
        device_id="missing-dev",
        preset_number=3,
        station_uuid="uuid-zzz",
        station_name="Ghost Station",
        station_url="http://ghost/stream.mp3",
    )

    assert result == saved_preset


# ---------------------------------------------------------------------------
# get_preset / get_all_presets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_preset_delegates_to_repository(service, mock_repo):
    expected = MagicMock()
    mock_repo.get_preset = AsyncMock(return_value=expected)

    result = await service.get_preset("dev-001", 1)

    assert result == expected
    mock_repo.get_preset.assert_called_once_with("dev-001", 1)


@pytest.mark.asyncio
async def test_get_all_presets_delegates_to_repository(service, mock_repo):
    expected = [MagicMock(), MagicMock()]
    mock_repo.get_all_presets = AsyncMock(return_value=expected)

    result = await service.get_all_presets("dev-001")

    assert result == expected
    mock_repo.get_all_presets.assert_called_once_with("dev-001")


# ---------------------------------------------------------------------------
# clear_preset / clear_all_presets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_preset_returns_true_when_deleted(service, mock_repo):
    mock_repo.clear_preset = AsyncMock(return_value=1)

    result = await service.clear_preset("dev-001", 1)

    assert result is True
    mock_repo.clear_preset.assert_called_once_with("dev-001", 1)


@pytest.mark.asyncio
async def test_clear_preset_returns_false_when_not_found(service, mock_repo):
    mock_repo.clear_preset = AsyncMock(return_value=0)

    result = await service.clear_preset("dev-001", 5)

    assert result is False


@pytest.mark.asyncio
async def test_clear_all_presets_returns_count(service, mock_repo):
    mock_repo.clear_all_presets = AsyncMock(return_value=4)

    count = await service.clear_all_presets("dev-001")

    assert count == 4
    mock_repo.clear_all_presets.assert_called_once_with("dev-001")
