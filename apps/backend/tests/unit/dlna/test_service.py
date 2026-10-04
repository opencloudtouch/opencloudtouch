"""Tests for the DLNA application service."""

from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.models import DlnaItem, DlnaServer
from opencloudtouch.dlna.service import DlnaService


@pytest.mark.asyncio
async def test_get_servers():
    server = DlnaServer(
        id="server-1",
        name="Test Server",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/content/control",
    )

    discovery = AsyncMock()
    discovery.discover.return_value = [server]

    service = DlnaService(discovery=discovery)

    result = await service.get_servers()

    assert result == [server]


@pytest.mark.asyncio
async def test_browse_server():
    server = DlnaServer(
        id="server-1",
        name="Test Server",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/content/control",
    )
    item = DlnaItem(
        id="track-1",
        parent_id="0",
        title="Track",
        is_container=False,
    )

    discovery = AsyncMock()
    discovery.discover.return_value = [server]

    client = AsyncMock()
    client.browse.return_value = [item]

    service = DlnaService(
        discovery=discovery,
        client=client,
    )

    result = await service.browse("server-1", "0")

    assert result == [item]
    client.browse.assert_awaited_once_with(server, "0")


@pytest.mark.asyncio
async def test_browse_unknown_server():
    discovery = AsyncMock()
    discovery.discover.return_value = []

    service = DlnaService(discovery=discovery)

    with pytest.raises(LookupError):
        await service.browse("missing-server")
