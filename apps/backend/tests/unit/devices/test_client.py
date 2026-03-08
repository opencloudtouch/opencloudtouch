"""
Tests for Device Client Adapter
"""

from unittest.mock import MagicMock, patch

import pytest

from opencloudtouch.devices.adapter import BoseDeviceClientAdapter
from opencloudtouch.devices.client import DeviceInfo


@pytest.mark.asyncio
async def test_get_info_success():
    """Test successful /info request."""
    # Mock SoundTouchDevice constructor to avoid actual network calls
    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        client = BoseDeviceClientAdapter("http://192.168.1.100:8090")

        # Mock BoseClient.GetInformation()
        mock_info = MagicMock()
        mock_info.DeviceId = "12345ABC"
        mock_info.DeviceName = "Living Room"  # Correct: DeviceName not Name
        mock_info.DeviceType = "SoundTouch 30"  # Correct: DeviceType not Type
        mock_info.MacAddress = "AA:BB:CC:DD:EE:FF"
        mock_info.ModuleType = "sm2"
        mock_info.Variant = "spotty"
        mock_info.VariantMode = "normal"

        # Mock firmware component
        mock_component = MagicMock()
        mock_component.SoftwareVersion = (
            "28.0.3.46454 epdbuild.trunk.hepdswbld02.2023-07-27T14:58:40"
        )
        mock_info.Components = [mock_component]

        mock_network = MagicMock()
        mock_network.MacAddress = "AA:BB:CC:DD:EE:FF"
        mock_network.IpAddress = "192.168.1.100"
        mock_info.NetworkInfo = [mock_network]  # Correct: NetworkInfo is a list

        client._client.GetInformation = MagicMock(return_value=mock_info)

        info = await client.get_info()

        assert isinstance(info, DeviceInfo)
        assert info.device_id == "12345ABC"
        assert info.name == "Living Room"
        assert info.type == "SoundTouch 30"
        assert info.mac_address == "AA:BB:CC:DD:EE:FF"
        assert info.ip_address == "192.168.1.100"
        assert (
            info.firmware_version
            == "28.0.3.46454 epdbuild.trunk.hepdswbld02.2023-07-27T14:58:40"
        )
        assert info.module_type == "sm2"
        assert info.variant == "spotty"


@pytest.mark.asyncio
async def test_get_info_firmware_logging(caplog):
    """Test that firmware details are logged on device initialization."""
    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        client = BoseDeviceClientAdapter("http://192.168.1.100:8090")

        # Mock device info with firmware
        mock_info = MagicMock()
        mock_info.DeviceId = "TEST123"
        mock_info.DeviceName = "Test Device"
        mock_info.DeviceType = "SoundTouch 300"
        mock_info.MacAddress = "11:22:33:44:55:66"
        mock_info.ModuleType = "sm2"
        mock_info.Variant = "hermosa"
        mock_info.VariantMode = "normal"

        mock_component = MagicMock()
        mock_component.SoftwareVersion = "28.0.3.46454"
        mock_info.Components = [mock_component]

        mock_network = MagicMock()
        mock_network.IpAddress = "192.168.1.200"
        mock_info.NetworkInfo = [mock_network]

        client._client.GetInformation = MagicMock(return_value=mock_info)

        # Capture logs
        import logging

        caplog.set_level(logging.INFO)

        await client.get_info()

        # Verify firmware logging
        assert any(
            "Device Test Device initialized" in record.message
            for record in caplog.records
        )


@pytest.mark.asyncio
async def test_get_now_playing_success():
    """Test successful /now_playing request."""
    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        client = BoseDeviceClientAdapter("http://192.168.1.100:8090")

        # Mock BoseClient.GetNowPlayingStatus() - Correct method name
        mock_now_playing = MagicMock()
        mock_now_playing.Source = "INTERNET_RADIO"
        mock_now_playing.PlayStatus = "PLAY_STATE"
        mock_now_playing.StationName = "Radio Station Name"  # Direct property
        mock_now_playing.Artist = None
        mock_now_playing.Track = None
        mock_now_playing.Album = None
        mock_now_playing.ArtUrl = (
            "http://example.com/art.jpg"  # Correct: ArtUrl not Art
        )
        mock_now_playing.ContentItem = MagicMock()

        client._client.GetNowPlayingStatus = MagicMock(
            return_value=mock_now_playing
        )  # Correct method


@pytest.mark.asyncio
async def test_get_info_connection_error():
    """Test /info request with connection error."""
    from opencloudtouch.core.exceptions import DeviceConnectionError

    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        client = BoseDeviceClientAdapter("http://192.168.1.100:8090")
        client._client.GetInformation = MagicMock(
            side_effect=Exception("Connection refused")
        )

        with pytest.raises(DeviceConnectionError):
            await client.get_info()


@pytest.mark.asyncio
async def test_parse_invalid_xml():
    """Test XML parsing with invalid response (library handles internally)."""
    from opencloudtouch.core.exceptions import DeviceConnectionError

    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        client = BoseDeviceClientAdapter("http://192.168.1.100:8090")

        # bosesoundtouchapi handles XML parsing internally
        # We test error propagation instead
        client._client.GetInformation = MagicMock(side_effect=Exception("Invalid XML"))

        with pytest.raises(DeviceConnectionError):
            await client.get_info()


def test_client_base_url_trailing_slash():
    """Test that trailing slash is removed from base_url."""
    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        client = BoseDeviceClientAdapter("http://192.168.1.100:8090/")

        assert client.base_url == "http://192.168.1.100:8090"


def test_connect_timeout_constructor_parameter_regression():
    """Regression test for ConnectTimeout initialization bug.

    Bug: Attempted to set device.ConnectTimeout after object creation,
         but ConnectTimeout is a read-only property.
    Error: "property 'ConnectTimeout' of 'SoundTouchDevice' object has no setter"
    Fixed: 2026-01-29 - Pass connectTimeout to SoundTouchDevice constructor.

    Root cause: SoundTouchDevice() accepts connectTimeout as __init__ parameter,
                but the property is read-only after initialization.
    Solution: Pass timeout via constructor: SoundTouchDevice(host=ip, connectTimeout=timeout)
    """
    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        # Create client with custom timeout
        client = BoseDeviceClientAdapter("http://192.168.1.100:8090", timeout=15.0)

        # Verify SoundTouchDevice was called with connectTimeout parameter
        mock_device_class.assert_called_once_with(
            host="192.168.1.100", connectTimeout=15, port=8090  # Should be int
        )

        # Verify client stores timeout
        assert client.timeout == 15.0


def test_connect_timeout_default_value():
    """Test that default timeout (5s) is properly passed to SoundTouchDevice."""
    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        # Create client without specifying timeout (use default)
        BoseDeviceClientAdapter("http://192.168.1.100:8090")

        # Verify default timeout (5.0) is passed
        mock_device_class.assert_called_once_with(
            host="192.168.1.100",
            connectTimeout=5,  # Default value, converted to int
            port=8090,
        )


def test_connect_timeout_custom_port():
    """Test timeout with custom port extraction from URL."""
    with patch(
        "opencloudtouch.devices.client_adapter.SoundTouchDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device_class.return_value = mock_device

        # Create client with custom port in URL
        BoseDeviceClientAdapter("http://192.168.1.100:9000", timeout=10.0)

        # Verify custom port is extracted and passed
        mock_device_class.assert_called_once_with(
            host="192.168.1.100", connectTimeout=10, port=9000  # Custom port from URL
        )
