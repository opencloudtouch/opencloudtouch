"""Tests for DLNA media server discovery."""

import itertools
import socket
from unittest.mock import AsyncMock, MagicMock, patch

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


def _fake_socket(responses=()):
    """Fake UDP socket: returns the given datagrams, then times out."""
    sock = MagicMock()
    sock.recvfrom.side_effect = itertools.chain(
        ((r, ("192.0.2.10", 1900)) for r in responses),
        itertools.repeat(socket.timeout()),
    )
    return sock


def _response(location: str) -> bytes:
    return f"HTTP/1.1 200 OK\r\nLOCATION: {location}\r\n\r\n".encode()


def test_msearch_binds_ephemeral_port_not_1900():
    sock = _fake_socket()
    with patch("opencloudtouch.dlna.discovery.socket.socket", return_value=sock):
        assert DlnaDiscovery(timeout=0.01)._msearch() == []
    sock.bind.assert_called_once_with(("", 0))
    sock.setsockopt.assert_called_once_with(
        socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2
    )
    sock.close.assert_called_once_with()


def test_msearch_message_has_mediaserver_target_and_mx():
    sock = _fake_socket()
    with patch("opencloudtouch.dlna.discovery.socket.socket", return_value=sock):
        DlnaDiscovery(timeout=0.01)._msearch()
    msg, addr = sock.sendto.call_args.args
    assert addr == ("239.255.255.250", 1900)
    text = msg.decode()
    assert text.startswith("M-SEARCH * HTTP/1.1\r\n")
    assert "HOST: 239.255.255.250:1900\r\n" in text
    assert 'MAN: "ssdp:discover"\r\n' in text
    assert "MX: 2\r\n" in text
    assert "ST: urn:schemas-upnp-org:device:MediaServer:1\r\n" in text


def test_collects_unique_locations_until_deadline():
    location = "http://192.0.2.10:8200/rootDesc.xml"
    no_location = b"HTTP/1.1 200 OK\r\n\r\n"
    sock = _fake_socket([_response(location), no_location, _response(location)])
    with patch("opencloudtouch.dlna.discovery.socket.socket", return_value=sock):
        assert DlnaDiscovery(timeout=0.05)._msearch() == [location]
    sock.close.assert_called_once_with()


def test_receive_error_keeps_collected_locations():
    location = "http://192.0.2.10:8200/rootDesc.xml"
    sock = MagicMock()
    sock.recvfrom.side_effect = [(_response(location), None), OSError("reset")]
    with patch("opencloudtouch.dlna.discovery.socket.socket", return_value=sock):
        assert DlnaDiscovery(timeout=5)._msearch() == [location]


def test_send_failure_returns_empty(caplog):
    sock = _fake_socket()
    sock.sendto.side_effect = OSError("network unreachable")
    with patch("opencloudtouch.dlna.discovery.socket.socket", return_value=sock):
        assert DlnaDiscovery(timeout=0.01)._msearch() == []
    assert [r.levelname for r in caplog.records] == ["WARNING"]
    sock.close.assert_called_once_with()


def test_socket_creation_failure_returns_empty():
    with patch(
        "opencloudtouch.dlna.discovery.socket.socket", side_effect=OSError("denied")
    ):
        assert DlnaDiscovery(timeout=0.01)._msearch() == []


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


@pytest.mark.asyncio
async def test_discover_parses_description_into_server(monkeypatch):
    discovery = DlnaDiscovery()
    locations = ["http://192.0.2.10:8200/root.xml"]
    search = MagicMock(return_value=locations)
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(discovery, "_msearch", search)
    monkeypatch.setattr(discovery, "_fetch_server_descriptions", fetch)

    assert await discovery.discover() == []
    search.assert_called_once_with()
    fetch.assert_awaited_once_with(locations)
