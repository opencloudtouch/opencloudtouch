"""Unit tests for BoseDeviceClientAdapter.

Directly imports from opencloudtouch.devices.client_adapter (STORY-305).
The class was extracted from adapter.py to give the Bose HTTP client adapter
its own focused module.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.client import DeviceInfo, NowPlayingInfo

# RED: This import fails until client_adapter.py is created.
from opencloudtouch.devices.client_adapter import BoseDeviceClientAdapter


def _make_client(base_url: str = "http://192.168.1.100:8090"):
    """Create BoseDeviceClientAdapter with mocked BoseClient."""
    with patch("opencloudtouch.devices.client_adapter.SoundTouchDevice"), patch(
        "opencloudtouch.devices.client_adapter.BoseClient"
    ):
        return BoseDeviceClientAdapter(base_url)


class TestBoseDeviceClientAdapterInit:
    """Tests for constructor / URL parsing."""

    def test_init_extracts_ip(self):
        """IP is extracted from base_url and stored."""
        client = _make_client("http://192.168.1.55:8090")
        assert client.ip == "192.168.1.55"

    def test_init_stores_base_url(self):
        """base_url is stored without trailing slash."""
        client = _make_client("http://192.168.1.55:8090/")
        assert client.base_url == "http://192.168.1.55:8090"

    def test_init_default_timeout(self):
        """Default timeout is 3.0 seconds."""
        client = _make_client()
        assert client.timeout == 3.0

    def test_init_custom_timeout(self):
        """Custom timeout is stored."""
        with patch("opencloudtouch.devices.client_adapter.SoundTouchDevice"), patch(
            "opencloudtouch.devices.client_adapter.BoseClient"
        ):
            client = BoseDeviceClientAdapter("http://192.168.1.100:8090", timeout=10.0)
        assert client.timeout == 10.0

    def test_init_raises_device_connection_error_when_device_unreachable(self):
        """Regression test for #82: offline device must raise DeviceConnectionError."""
        with patch(
            "opencloudtouch.devices.client_adapter.SoundTouchDevice",
            side_effect=Exception(
                "HTTPConnectionPool(host='192.168.178.48', port=8090): "
                "Max retries exceeded with url: /info"
            ),
        ):
            with pytest.raises(DeviceConnectionError) as exc_info:
                BoseDeviceClientAdapter("http://192.168.178.48:8090")
            assert "192.168.178.48" in str(exc_info.value)

    def test_init_raises_device_connection_error_on_no_route(self):
        """Regression test for #82: No route to host raises DeviceConnectionError."""
        with patch(
            "opencloudtouch.devices.client_adapter.SoundTouchDevice",
            side_effect=OSError("[Errno 113] No route to host"),
        ):
            with pytest.raises(DeviceConnectionError):
                BoseDeviceClientAdapter("http://192.168.178.48:8090")

    def test_init_raises_device_connection_error_on_timeout(self):
        """Regression test for #82: connection timeout raises DeviceConnectionError."""
        with patch(
            "opencloudtouch.devices.client_adapter.SoundTouchDevice",
            side_effect=TimeoutError("connection timed out"),
        ):
            with pytest.raises(DeviceConnectionError):
                BoseDeviceClientAdapter("http://192.168.1.100:8090")


class TestExtractFirmwareVersion:
    """Tests for _extract_firmware_version helper."""

    def test_returns_empty_when_no_components(self):
        client = _make_client()
        info = MagicMock(spec=[])  # no Components attr
        assert client._extract_firmware_version(info) == ""

    def test_returns_empty_when_components_empty(self):
        client = _make_client()
        info = MagicMock()
        info.Components = []
        assert client._extract_firmware_version(info) == ""

    def test_returns_software_version_from_first_component(self):
        client = _make_client()
        component = MagicMock()
        component.SoftwareVersion = "28.0.12.46499"
        info = MagicMock()
        info.Components = [component]
        assert client._extract_firmware_version(info) == "28.0.12.46499"


class TestExtractIpAddress:
    """Tests for _extract_ip_address helper."""

    def test_falls_back_to_self_ip_when_no_network_info(self):
        client = _make_client("http://192.168.1.100:8090")
        info = MagicMock()
        info.NetworkInfo = []
        assert client._extract_ip_address(info) == "192.168.1.100"

    def test_returns_ip_from_network_info(self):
        client = _make_client("http://192.168.1.100:8090")
        net = MagicMock()
        net.IpAddress = "192.168.1.200"
        info = MagicMock()
        info.NetworkInfo = [net]
        assert client._extract_ip_address(info) == "192.168.1.200"


class TestGetInfo:
    """Tests for get_info()."""

    @pytest.mark.asyncio
    async def test_returns_device_info_on_success(self):
        client = _make_client()
        mock_info = MagicMock()
        mock_info.DeviceId = "ABC123"
        mock_info.DeviceName = "Living Room"
        mock_info.DeviceType = "SoundTouch 20"
        mock_info.Components = []
        mock_info.NetworkInfo = []
        client._client.GetInformation.return_value = mock_info

        result = await client.get_info()

        assert isinstance(result, DeviceInfo)
        assert result.device_id == "ABC123"
        assert result.name == "Living Room"

    @pytest.mark.asyncio
    async def test_raises_device_connection_error_on_failure(self):
        client = _make_client()
        client._client.GetInformation.side_effect = RuntimeError("timeout")

        with pytest.raises(DeviceConnectionError):
            await client.get_info()


class TestGetNowPlaying:
    """Tests for get_now_playing()."""

    @pytest.mark.asyncio
    async def test_returns_now_playing_info(self):
        client = _make_client()
        mock_status = MagicMock()
        mock_status.PlayStatus = "PLAY_STATE"
        mock_status.Source = "INTERNET_RADIO"
        client._client.GetNowPlayingStatus.return_value = mock_status

        result = await client.get_now_playing()

        assert isinstance(result, NowPlayingInfo)
        assert result.state == "PLAY_STATE"
        assert result.source == "INTERNET_RADIO"

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        client = _make_client()
        client._client.GetNowPlayingStatus.side_effect = RuntimeError("conn error")

        with pytest.raises(DeviceConnectionError):
            await client.get_now_playing()


class TestStorePreset:
    """Tests for store_preset()."""

    @pytest.mark.asyncio
    async def test_raises_for_invalid_preset_number(self):
        client = _make_client()
        with pytest.raises(ValueError, match="Preset number must be 1-6"):
            await client.store_preset("D1", 7, "http://stream", "Station", "http://oct")

    @pytest.mark.asyncio
    async def test_posts_to_store_preset_endpoint(self):
        import httpx
        import respx

        client = _make_client("http://192.168.1.100:8090")

        with respx.mock:
            route = respx.post("http://192.168.1.100:8090/storePreset").mock(
                return_value=httpx.Response(200)
            )
            await client.store_preset(
                "DEVICE1", 1, "http://radio.stream/mp3", "MyStation", "http://oct:7777"
            )
            assert route.called


class TestClose:
    """Tests for close()."""

    @pytest.mark.asyncio
    async def test_close_is_noop(self):
        """close() must not raise."""
        client = _make_client()
        await client.close()  # Should not raise


class TestSetName:
    """Tests for set_name() method (REST API /name endpoint)."""

    @pytest.mark.asyncio
    async def test_set_name_success(self, respx_mock):
        """Test successful device rename via POST /name."""
        respx_mock.post("http://192.168.1.100:8090/name").mock(
            return_value=httpx.Response(200, text="<info><name>New Name</name></info>")
        )

        client = _make_client()
        await client.set_name("New Name")

        # Verify request
        assert len(respx_mock.calls) == 1
        request = respx_mock.calls[0].request
        assert request.method == "POST"
        assert request.url.path == "/name"
        assert b"<name>New Name</name>" in request.content

    @pytest.mark.asyncio
    async def test_set_name_xml_escapes_special_chars(self, respx_mock):
        """Test that special XML characters are escaped."""
        respx_mock.post("http://192.168.1.100:8090/name").mock(
            return_value=httpx.Response(200)
        )

        client = _make_client()
        await client.set_name("Room <1> & 'Test'")

        request = respx_mock.calls[0].request
        assert b"&lt;1&gt;" in request.content  # < escaped
        assert b"&amp;" in request.content  # & escaped
        # Note: Single quotes don't need escaping in XML element content

    @pytest.mark.asyncio
    async def test_set_name_strips_whitespace(self, respx_mock):
        """Test that leading/trailing whitespace is stripped."""
        respx_mock.post("http://192.168.1.100:8090/name").mock(
            return_value=httpx.Response(200)
        )

        client = _make_client()
        await client.set_name("  Trimmed  ")

        request = respx_mock.calls[0].request
        assert b"<name>Trimmed</name>" in request.content

    @pytest.mark.asyncio
    async def test_set_name_empty_raises_value_error(self):
        """Test that empty name raises ValueError."""
        client = _make_client()
        with pytest.raises(ValueError, match="cannot be empty"):
            await client.set_name("")

    @pytest.mark.asyncio
    async def test_set_name_whitespace_only_raises_value_error(self):
        """Test that whitespace-only name raises ValueError."""
        client = _make_client()
        with pytest.raises(ValueError, match="cannot be empty"):
            await client.set_name("   ")

    @pytest.mark.asyncio
    async def test_set_name_too_long_raises_value_error(self):
        """Test that name > 30 chars raises ValueError."""
        client = _make_client()
        with pytest.raises(ValueError, match="30 characters or fewer"):
            await client.set_name("A" * 31)

    @pytest.mark.asyncio
    async def test_set_name_http_error_raises_device_connection_error(self, respx_mock):
        """Test that HTTP error raises DeviceConnectionError."""
        respx_mock.post("http://192.168.1.100:8090/name").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        client = _make_client()
        with pytest.raises(DeviceConnectionError, match="192.168.1.100"):
            await client.set_name("New Name")

    @pytest.mark.asyncio
    async def test_set_name_network_error_raises_device_connection_error(
        self, respx_mock
    ):
        """Test that network error raises DeviceConnectionError."""
        respx_mock.post("http://192.168.1.100:8090/name").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        client = _make_client()
        with pytest.raises(DeviceConnectionError):
            await client.set_name("New Name")
