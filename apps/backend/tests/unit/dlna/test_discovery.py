"""Tests for DLNA media server discovery."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.devices.discovery.ssdp import SSDPDiscovery

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

    assert (
        discovery.ssdp._parse_location(response)
        == "http://192.0.2.10:8200/rootDesc.xml"
    )


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


def test_dlna_reuses_shared_ssdp_target():
    discovery = DlnaDiscovery(timeout=7)
    assert isinstance(discovery.ssdp, SSDPDiscovery)
    assert discovery.ssdp.timeout == 7
    assert discovery.ssdp.search_target == discovery.SEARCH_TARGET
    assert SSDPDiscovery().search_target == "ssdp:all"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://192.168.55.45:8200/root.xml", True),
        ("http://nas.local:8200/root.xml", True),
        ("http://127.0.0.1/admin", False),
        ("http://0.0.0.0/", False),
        ("http://239.255.255.250:1900/", False),
        ("file:///etc/passwd", False),
        ("http://user:pass@192.168.55.45/", False),
        ("http://192.168.55.45:bad/", False),
    ],
)
def test_location_validation(url, expected):
    assert DlnaDiscovery._valid_http_url(url) is expected


@pytest.mark.asyncio
async def test_reject_control_url_to_different_host():
    discovery = DlnaDiscovery()
    response = MagicMock()
    response.text = DEVICE_DESCRIPTION.replace(
        "/ContentDirectory/control", "http://127.0.0.1:9999/admin"
    )
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get.return_value = response
    server = await discovery._fetch_and_parse_server(
        client, "http://192.168.55.30:8200/root.xml"
    )
    assert server is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://192.168.55.1:49000/MediaServerDevDesc.xml", True),
        ("http://[fd00::45]:8200/root.xml", True),
        ("http://nas.local:8200/root.xml", True),
        ("http://localhost:8200/root.xml", False),
        ("http://service.localhost:8200/root.xml", False),
        ("http://127.0.0.1:8200/root.xml", False),
        ("http://[::1]:8200/root.xml", False),
        ("http://0.0.0.0:8200/root.xml", False),
        ("ftp://192.168.55.1/file", False),
        ("http://user:password@192.168.55.1/root.xml", False),
    ],
)
def test_dlna_url_sanity_checks(url, expected):
    assert DlnaDiscovery._valid_http_url(url) is expected


def test_dlna_control_url_must_match_description_host():
    assert DlnaDiscovery._valid_http_url(
        "http://192.168.55.1:49000/MediaServer/ContentDirectory/Control",
        expected_host="192.168.55.1",
    )

    assert not DlnaDiscovery._valid_http_url(
        "http://192.168.55.99:8200/control",
        expected_host="192.168.55.1",
    )
