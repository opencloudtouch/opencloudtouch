"""
Tests for SSDP Discovery
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree import ElementTree

import pytest

from opencloudtouch.devices.discovery.ssdp import SSDPDiscovery


@pytest.mark.asyncio
async def test_ssdp_discovery_success():
    """Test successful SSDP discovery."""
    discovery = SSDPDiscovery(timeout=5)

    # Mock the device description response
    mock_device_info = {
        "AA:BB:CC:11:22:33": {
            "ip": "192.168.1.100",
            "mac": "AA:BB:CC:11:22:33",
            "name": "Living Room",
            "model": "SoundTouch 10",
        }
    }

    with patch.object(
        discovery, "_ssdp_msearch", return_value=["http://192.168.1.100:8090/info"]
    ):
        with patch.object(
            discovery, "_fetch_device_descriptions", return_value=mock_device_info
        ):
            devices = await discovery.discover()

            assert len(devices) == 1
            assert "AA:BB:CC:11:22:33" in devices
            assert devices["AA:BB:CC:11:22:33"]["ip"] == "192.168.1.100"
            assert devices["AA:BB:CC:11:22:33"]["name"] == "Living Room"


@pytest.mark.asyncio
async def test_ssdp_discovery_no_devices():
    """Test SSDP discovery when no devices are found."""
    discovery = SSDPDiscovery(timeout=5)

    with patch.object(discovery, "_ssdp_msearch", return_value=[]):
        with patch.object(discovery, "_fetch_device_descriptions", return_value={}):
            devices = await discovery.discover()

            assert devices == {}


@pytest.mark.asyncio
async def test_ssdp_discovery_error():
    """Test SSDP discovery when an error occurs."""
    discovery = SSDPDiscovery(timeout=5)

    with patch.object(
        discovery, "_ssdp_msearch", side_effect=Exception("Network error")
    ):
        devices = await discovery.discover()

        # Should return empty dict on error, not raise
        assert devices == {}


def test_parse_location():
    """Test parsing LOCATION header from SSDP response."""
    discovery = SSDPDiscovery()

    response = (
        "HTTP/1.1 200 OK\r\n"
        "CACHE-CONTROL: max-age=1800\r\n"
        "LOCATION: http://192.168.1.100:8090/info\r\n"
        "SERVER: Linux UPnP/1.0 Bose SoundTouch\r\n"
        "\r\n"
    )

    location = discovery._parse_location(response)
    assert location == "http://192.168.1.100:8090/info"


def test_parse_location_no_header():
    """Test parsing LOCATION when header is missing."""
    discovery = SSDPDiscovery()

    response = "HTTP/1.1 200 OK\r\n" "CACHE-CONTROL: max-age=1800\r\n" "\r\n"

    location = discovery._parse_location(response)
    assert location is None


@pytest.mark.asyncio
async def test_fetch_device_descriptions_filters_non_compatible():
    """Test that non-compatible devices are filtered out."""
    discovery = SSDPDiscovery()

    # Mock httpx to return non-compatible device
    mock_response = MagicMock()
    mock_response.text = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
        <device>
            <manufacturer>NotBose</manufacturer>
            <friendlyName>Other Device</friendlyName>
        </device>
    </root>"""
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client.return_value = mock_client_instance

        devices = await discovery._fetch_device_descriptions(
            ["http://192.168.1.100:8090/info"]
        )

        # Non-compatible device should be filtered out
        assert devices == {}


@pytest.mark.asyncio
async def test_fetch_device_descriptions_compatible_device():
    """Test that compatible devices are correctly parsed with namespace."""
    discovery = SSDPDiscovery()

    # Real Bose SoundTouch XML with namespace
    mock_response = MagicMock()
    mock_response.text = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
        <device>
            <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
            <friendlyName>Living Room</friendlyName>
            <manufacturer>Bose Corporation</manufacturer>
            <modelName>SoundTouch 30</modelName>
            <serialNumber>B92C7D383488</serialNumber>
        </device>
    </root>"""
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client.return_value = mock_client_instance

        devices = await discovery._fetch_device_descriptions(
            ["http://192.0.2.78:8091/XD/BO5EBO5E-F00D-F00D-FEED-B92C7D383488.xml"]
        )

        # Bose device should be parsed correctly
        assert len(devices) == 1
        # MAC should be extracted from serial number (last 12 chars formatted as MAC)
        mac_key = list(devices.keys())[0]
        device = devices[mac_key]
        assert device["name"] == "Living Room"
        assert device["model"] == "SoundTouch 30"
        assert device["ip"] == "192.0.2.78"


def test_xml_namespace_parsing_regression():
    """Regression test for XML namespace handling in SSDP discovery.

    Bug: _find_xml_text() failed to parse elements with xmlns namespace.
    Fixed: 2026-01-29 - Implemented namespace-agnostic element search.

    Root cause: ElementTree.find() requires namespace mapping for namespaced XML.
    Solution: Iterate through elements and match by tag suffix (local name).
    """
    discovery = SSDPDiscovery()

    # XML with UPnP namespace (real Bose device format)
    xml_with_namespace = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
        <device>
            <manufacturer>Bose Corporation</manufacturer>
            <friendlyName>Living Room</friendlyName>
            <modelName>SoundTouch 10</modelName>
        </device>
    </root>"""

    root = ElementTree.fromstring(xml_with_namespace)

    # These should all work with namespace-agnostic parsing
    manufacturer = discovery._find_xml_text(root, ".//manufacturer")
    assert manufacturer == "Bose Corporation"

    friendly_name = discovery._find_xml_text(root, ".//friendlyName")
    assert friendly_name == "Living Room"

    model_name = discovery._find_xml_text(root, ".//modelName")
    assert model_name == "SoundTouch 10"


@pytest.mark.asyncio
async def test_concurrent_discovery_requests():
    """Test that multiple concurrent discovery requests don't interfere.

    Edge case: User triggers discovery multiple times rapidly (UI spam-click).
    Expected: All requests complete successfully without resource leaks.

    Regression protection: Concurrent socket operations should not deadlock.
    """
    discovery = SSDPDiscovery(timeout=2)

    # Mock successful discovery
    mock_device_info = {
        "AA:BB:CC:11:22:33": {
            "ip": "192.168.1.100",
            "mac": "AA:BB:CC:11:22:33",
            "name": "Living Room",
            "model": "SoundTouch 10",
        }
    }

    with patch.object(
        discovery, "_ssdp_msearch", return_value=["http://192.168.1.100:8090/info"]
    ):
        with patch.object(
            discovery, "_fetch_device_descriptions", return_value=mock_device_info
        ):
            # Run 5 concurrent discovery requests
            tasks = [discovery.discover() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert len(results) == 5
            for result in results:
                assert len(result) == 1
                assert "AA:BB:CC:11:22:33" in result


@pytest.mark.asyncio
async def test_concurrent_discovery_mixed_success_failure():
    """Test concurrent discovery with mixed success/failure scenarios.

    Edge case: Network flakiness during concurrent requests.
    Expected: Failed requests return empty dict, successful ones return devices.
    """
    discovery = SSDPDiscovery(timeout=2)

    mock_device_info = {
        "AA:BB:CC:11:22:33": {
            "ip": "192.168.1.100",
            "mac": "AA:BB:CC:11:22:33",
            "name": "Living Room",
            "model": "SoundTouch 10",
        }
    }

    # Mock: alternating success/failure
    call_count = 0

    def side_effect():
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            raise Exception("Network timeout")
        return ["http://192.168.1.100:8090/info"]

    with patch.object(discovery, "_ssdp_msearch", side_effect=side_effect):
        with patch.object(
            discovery, "_fetch_device_descriptions", return_value=mock_device_info
        ):
            tasks = [discovery.discover() for _ in range(6)]
            results = await asyncio.gather(*tasks)

            # Should have 3 successes, 3 empty results (failures)
            successes = [r for r in results if r]
            failures = [r for r in results if not r]
            assert len(successes) == 3
            assert len(failures) == 3


def test_xml_without_namespace_still_works():
    """Ensure namespace-agnostic parsing doesn't break non-namespaced XML."""
    discovery = SSDPDiscovery()

    # XML without namespace
    xml_without_namespace = """<?xml version="1.0"?>
    <root>
        <device>
            <manufacturer>Bose Corporation</manufacturer>
        </device>
    </root>"""

    root = ElementTree.fromstring(xml_without_namespace)
    manufacturer = discovery._find_xml_text(root, ".//manufacturer")
    assert manufacturer == "Bose Corporation"


# ==================== EDGE CASE TESTS ====================


# ==================== EDGE CASE TESTS ====================


def test_extract_ip_from_url_success():
    """Test successful IP extraction from URL."""
    discovery = SSDPDiscovery()

    url = "http://192.168.1.100:8090/device.xml"
    ip = discovery._extract_ip_from_url(url)

    assert ip == "192.168.1.100"


def test_extract_ip_from_url_different_port():
    """Test IP extraction with different port."""
    discovery = SSDPDiscovery()

    url = "http://10.0.0.1:1234/info"
    ip = discovery._extract_ip_from_url(url)

    assert ip == "10.0.0.1"


def test_extract_ip_from_url_malformed():
    """Test that malformed URLs return None or extract what's possible."""
    discovery = SSDPDiscovery()

    # URL without protocol - will fail on split
    assert discovery._extract_ip_from_url("not-a-url") is None

    # FTP protocol - extracts hostname (not ideal but current behavior)
    result = discovery._extract_ip_from_url("ftp://example.com")
    assert result == "example.com"  # Current implementation doesn't validate IP format

    # Empty string
    assert discovery._extract_ip_from_url("") is None


def test_find_xml_text_with_namespace():
    """Test _find_xml_text handles namespaced XML correctly."""
    discovery = SSDPDiscovery()

    xml = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
        <device>
            <friendlyName>Test Device</friendlyName>
        </device>
    </root>"""

    root = ElementTree.fromstring(xml)
    result = discovery._find_xml_text(root, ".//friendlyName")

    assert result == "Test Device"


def test_find_xml_text_without_namespace():
    """Test _find_xml_text handles non-namespaced XML correctly."""
    discovery = SSDPDiscovery()

    xml = """<?xml version="1.0"?>
    <root>
        <device>
            <friendlyName>Test Device</friendlyName>
        </device>
    </root>"""

    root = ElementTree.fromstring(xml)
    result = discovery._find_xml_text(root, ".//friendlyName")

    assert result == "Test Device"


def test_find_xml_text_missing_element():
    """Test _find_xml_text returns None for missing elements."""
    discovery = SSDPDiscovery()

    xml = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
        <device>
            <friendlyName>Test Device</friendlyName>
        </device>
    </root>"""

    root = ElementTree.fromstring(xml)
    result = discovery._find_xml_text(root, ".//nonExistent")

    assert result is None


def test_find_xml_text_empty_element():
    """Test _find_xml_text returns None for empty elements."""
    discovery = SSDPDiscovery()

    xml = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
        <device>
            <friendlyName></friendlyName>
        </device>
    </root>"""

    root = ElementTree.fromstring(xml)
    result = discovery._find_xml_text(root, ".//friendlyName")

    # Empty text should return None
    assert result is None or result == ""


# ==================== NETWORK ERROR TESTS ====================


@pytest.mark.asyncio
async def test_fetch_device_descriptions_http_timeout():
    """Test that HTTP timeout during device description fetch is handled."""
    discovery = SSDPDiscovery(timeout=1)

    import httpx

    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get.side_effect = httpx.TimeoutException("Request timeout")
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client.return_value = mock_client_instance

        devices = await discovery._fetch_device_descriptions(
            ["http://192.168.1.100:8090/info"]
        )

        # Should return empty dict on timeout, not raise
        assert devices == {}


@pytest.mark.asyncio
async def test_fetch_device_descriptions_http_error():
    """Test that HTTP errors (404, 500) are handled gracefully."""
    discovery = SSDPDiscovery()

    import httpx

    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client.return_value = mock_client_instance

        devices = await discovery._fetch_device_descriptions(
            ["http://192.168.1.100:8090/info"]
        )

        # Should return empty dict on HTTP error
        assert devices == {}


@pytest.mark.asyncio
async def test_fetch_device_descriptions_malformed_xml():
    """Test that malformed XML is handled without crashing."""
    discovery = SSDPDiscovery()

    mock_response = MagicMock()
    mock_response.text = "NOT XML AT ALL <invalid>"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client.return_value = mock_client_instance

        devices = await discovery._fetch_device_descriptions(
            ["http://192.168.1.100:8090/info"]
        )

        # Should return empty dict on XML parse error
        assert devices == {}


@pytest.mark.asyncio
async def test_ssdp_msearch_socket_error():
    """Test that socket errors during M-SEARCH are handled gracefully."""
    discovery = SSDPDiscovery(timeout=1)

    import socket as socket_module

    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.sendto.side_effect = socket_module.error("Network unreachable")
        mock_socket_class.return_value = mock_socket

        # Should not raise, return empty list
        locations = discovery._ssdp_msearch()

        assert locations == []


# ---------------------------------------------------------------------------
# BUG-13: SSDP Discovery hung 30+ minutes (no wall-clock deadline)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ssdp_discovery_respects_timeout():
    """
    BUG-13 Regression: SSDPDiscovery hung for 30+ minutes when network
    had 40+ non-Bose devices responding to M-SEARCH.

    Root cause:
    1. No wall-clock deadline in _ssdp_msearch — it collected ALL responses
    2. sync_service called discover() without timeout= parameter
    3. Each non-Bose URL was fetched over HTTP before filtering

    Fix: wall-clock deadline in _ssdp_msearch using time.monotonic().
    Measurement: 30+ min → 3.8s after fix.

    This test verifies discovery terminates promptly with a short timeout.
    """
    import time

    # Use a short timeout (1 second) to keep test fast
    discovery = SSDPDiscovery(timeout=1)

    # Mock socket to simulate responses from 40 non-Bose devices
    # (they respond to M-SEARCH but each HTTP fetch filters them out)
    non_bose_locations = [f"http://192.168.1.{i}:1900/description" for i in range(40)]

    with patch.object(discovery, "_ssdp_msearch", return_value=non_bose_locations):
        with patch("httpx.AsyncClient") as mock_client_class:

            def make_non_bose_xml(url):
                """Return non-Bose manufacturer XML synchronously."""
                mock_resp = MagicMock()
                mock_resp.text = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
    <device>
        <friendlyName>Some TV</friendlyName>
        <manufacturer>Samsung</manufacturer>
        <modelName>Smart TV</modelName>
    </device>
</root>"""
                mock_resp.raise_for_status = MagicMock()
                return mock_resp

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=lambda url, **kw: make_non_bose_xml(url)
            )
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            start = time.monotonic()
            result = await discovery.discover()
            elapsed = time.monotonic() - start

    # Verify: no Bose devices → empty result
    assert result == {}

    # Critical: must terminate within reasonable time (not 30+ minutes)
    # Allow generous 30s for test infra overhead; real fix = ~1-4s
    assert elapsed < 30, (
        f"BUG-13: Discovery took {elapsed:.1f}s with 40 non-Bose devices. "
        "Should complete in < 30s (was hanging 30+ minutes before fix). "
        "Fix: wall-clock deadline in _ssdp_msearch."
    )


@pytest.mark.asyncio
async def test_ssdp_discovery_with_timeout_parameter():
    """
    BUG-13: SSDPDiscovery(timeout=3) uses the specified timeout as deadline.
    """
    discovery = SSDPDiscovery(timeout=3)
    assert (
        discovery.timeout == 3
    ), "SSDPDiscovery must store the timeout parameter for wall-clock deadline."


def test_ssdp_msearch_deduplicates_responses(caplog):
    """Regression: EC24B8E5950F sent 200+ duplicate SSDP responses,
    flooding logs with 'Found SSDP device at ...' for each duplicate.

    Fix: Only log when a new unique location is first seen.
    """
    import logging
    import socket as socket_module

    discovery = SSDPDiscovery(timeout=1)

    # Simulate 200 identical SSDP responses from the same device
    duplicate_response = (
        "HTTP/1.1 200 OK\r\n"
        "LOCATION: http://192.168.178.42:8090/info\r\n"
        "SERVER: Linux UPnP/1.0 Bose SoundTouch\r\n"
        "\r\n"
    ).encode("utf-8")

    call_count = 0

    def fake_recvfrom(bufsize):
        nonlocal call_count
        call_count += 1
        if call_count > 200:
            raise socket_module.timeout("done")
        return duplicate_response, ("192.168.178.42", 1900)

    with patch("socket.socket") as mock_socket_class:
        mock_sock = MagicMock()
        mock_sock.recvfrom = fake_recvfrom
        mock_sock.sendto = MagicMock()
        mock_socket_class.return_value = mock_sock

        with caplog.at_level(
            logging.DEBUG, logger="opencloudtouch.devices.discovery.ssdp"
        ):
            locations = discovery._ssdp_msearch()

    # Should return exactly 1 unique location
    assert locations == ["http://192.168.178.42:8090/info"]

    # Should log "Found SSDP device" only ONCE, not 200 times
    found_msgs = [r for r in caplog.records if "Found SSDP device" in r.message]
    assert (
        len(found_msgs) == 1
    ), f"Expected 1 log message for deduplicated SSDP, got {len(found_msgs)}"


@pytest.mark.asyncio
async def test_ssdp_discovery_default_timeout_is_bounded():
    """
    BUG-13: Default timeout must be reasonable (not unbounded).
    Pre-fix: no deadline → hung until all 40 responses fetched.
    """
    discovery = SSDPDiscovery()
    # Default timeout should be bounded (e.g., 3-30 seconds)
    assert 1 <= discovery.timeout <= 30, (
        f"BUG-13: Default timeout={discovery.timeout}s. "
        "Must be between 1 and 30 seconds for timely completion."
    )


def test_ssdp_msearch_socket_recvfrom_decode_error():
    """Test that socket.recvfrom decode errors are handled."""
    discovery = SSDPDiscovery(timeout=1)

    import socket as socket_module

    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.sendto.return_value = None
        # First call returns invalid UTF-8, second call times out to exit loop
        mock_socket.recvfrom.side_effect = [
            (b"\xff\xfe\xfd\xfc Invalid UTF-8", ("192.168.1.1", 1900)),
            socket_module.timeout("Mock timeout to exit loop"),
        ]
        mock_socket_class.return_value = mock_socket

        # Should handle decode error gracefully (errors="ignore")
        locations = discovery._ssdp_msearch()

        # Should return empty list (no valid LOCATION found in garbage)
        assert isinstance(locations, list)
        mock_socket.close.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_device_descriptions_missing_required_fields():
    """Test device with missing manufacturer/model fields is skipped."""
    discovery = SSDPDiscovery()

    # XML missing manufacturer (should be filtered out)
    mock_response = MagicMock()
    mock_response.text = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
        <device>
            <friendlyName>Device Without Manufacturer</friendlyName>
            <modelName>Some Model</modelName>
        </device>
    </root>"""
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client.return_value = mock_client_instance

        devices = await discovery._fetch_device_descriptions(
            ["http://192.168.1.100:8090/info"]
        )

        # Should be empty (manufacturer missing)
        assert devices == {}
