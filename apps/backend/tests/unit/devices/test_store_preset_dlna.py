"""store_preset with a DLNA reference: per-source payload branch (AC-B1, AC-B11)."""

import base64
import json
import re
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from opencloudtouch.core.dlna_reference import (
    DlnaReference,
    DlnaReferenceTooLongError,
    parse_orion_data,
)
from opencloudtouch.devices.adapter import BoseDeviceClientAdapter
from opencloudtouch.devices.mock_client import MockDeviceClient

BASE = "http://oct.local:7777"
REF = DlnaReference("udn-1", "item/1")


@pytest.fixture
def adapter():
    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice",
        return_value=MagicMock(),
    ):
        return BoseDeviceClientAdapter("http://192.168.1.79:8090")


async def _store(adapter, ref, name="Song", image=""):
    captured = {}

    async def post(url, content, headers):
        captured["content"] = content
        return MagicMock()

    with patch("httpx.AsyncClient") as cls:
        client = AsyncMock()
        client.post = post
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        cls.return_value = client
        await adapter.store_preset(
            device_id="D",
            preset_number=2,
            station_url="dlna://udn-1/item%2F1",
            station_name=name,
            oct_backend_url=BASE,
            station_image_url=image,
            station_uuid="dlna-0123456789abcdef",
            dlna_reference=ref,
        )
    return captured["content"]


@pytest.mark.asyncio
async def test_dlna_payload_has_reference_only(adapter):
    xml = await _store(adapter, REF, image="http://nas/cover.jpg")
    location = re.search(r'location="([^"]+)"', xml).group(1)
    data = parse_qs(urlparse(location).query)["data"][0]
    assert parse_orion_data(data) == (REF, "Song")
    raw = json.loads(base64.urlsafe_b64decode(data))
    assert set(raw) == {"dlna", "name"}  # no streamUrl, tuneinId, imageUrl
    assert 'source="LOCAL_INTERNET_RADIO"' in xml
    assert "<containerArt>http://nas/cover.jpg</containerArt>" in xml


@pytest.mark.asyncio
async def test_dlna_payload_too_long_is_not_wrapped(adapter):
    with pytest.raises(DlnaReferenceTooLongError):
        await _store(adapter, DlnaReference("udn-1", "ü" * 512), name="ü" * 200)


@pytest.mark.asyncio
async def test_mock_client_enforces_limit_too():
    client = MockDeviceClient("DDEEFF445566")
    await client.store_preset("D", 1, "dlna://x/y", "Song", BASE, dlna_reference=REF)
    with pytest.raises(DlnaReferenceTooLongError):
        await client.store_preset(
            "D",
            1,
            "dlna://x/y",
            "ü" * 200,
            BASE,
            dlna_reference=DlnaReference("udn-1", "ü" * 512),
        )
