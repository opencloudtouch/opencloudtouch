"""Tests for DLNA media server discovery."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.dlna.discovery import DlnaDiscovery

DEVICE_DESCRIPTION = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>
    <friendlyName>Test Media Server</friendlyName>
    <UDN>uuid:12345678-1234-1234-1234-123456789abc</UDN>
    <serviceList>
      <service>
        <serviceType>
          urn:schemas-upnp-org:service:ContentDirectory:1
        </serviceType>
        <serviceId>urn:upnp-org:serviceId:ContentDirectory</serviceId>
        <controlURL>/ContentDirectory/control</controlURL>
      </service>
    </serviceList>
  </device>
</root>
"""


def test_parse_location():
    discovery = DlnaDiscovery()

    response = (
        "HTTP/1.1 200 OK\r\n"
        "CACHE-CONTROL: max-age=1800\r\n"
        "LOCATION: http://192.0.2.10:8200/rootDesc.xml\r\n"
        "\r\n"
    )

    assert discovery._parse_location(response) == "http://192.0.2.10:8200/rootDesc.xml"


@pytest.mark.asyncio
async def test_parse_media_server_description():
    discovery = DlnaDiscovery()

    response = MagicMock()
    response.text = DEVICE_DESCRIPTION
    response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.get.return_value = response

    server = await discovery._fetch_and_parse_server(
        client,
        "http://192.0.2.10:8200/rootDesc.xml",
    )

    assert server is not None
    assert server.id == "12345678-1234-1234-1234-123456789abc"
    assert server.name == "Test Media Server"
    assert server.location == "http://192.0.2.10:8200/rootDesc.xml"
    assert server.control_url == "http://192.0.2.10:8200/ContentDirectory/control"


@pytest.mark.asyncio
async def test_ignore_non_media_server():
    discovery = DlnaDiscovery()

    response = MagicMock()
    response.text = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
      <device>
        <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
        <friendlyName>Renderer</friendlyName>
        <UDN>uuid:renderer-id</UDN>
      </device>
    </root>
    """
    response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.get.return_value = response

    server = await discovery._fetch_and_parse_server(
        client,
        "http://192.0.2.20/device.xml",
    )

    assert server is None
