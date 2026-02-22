"""Unit tests for Bose device store_preset functionality.

**CRITICAL KNOWLEDGE** (Discovered 2026-02-22):

This module tests the preset storage workflow that enables radio station playback
on Bose SoundTouch devices AFTER the Bose Cloud shutdown.

## Why These Tests Are Critical

1. **BoseSoundTouchAPI Library Bug**: The library's `StorePreset()` method
   SILENTLY FAILS - it logs success but the device's preset is NOT updated.
   We MUST use direct HTTP POST to `/storePreset`.

2. **LOCAL_INTERNET_RADIO + Orion Pattern**: The ONLY working pattern is:
   - Source: `LOCAL_INTERNET_RADIO` (not TuneIn, not STORED_MUSIC)
   - Location: Orion adapter URL with base64-encoded stream data
   - The device fetches the Orion URL, OCT decodes and returns stream URL

3. **HTTPS Incompatibility**: Bose firmware CANNOT play HTTPS streams.
   All HTTPS URLs must be converted to HTTP.

## The Working Flow

```
User sets preset in UI
        ↓
OCT builds: `location="{oct_url}/core02/svc-bmx-adapter-orion/prod/orion/station?data={base64}"`
        ↓
OCT POSTs XML to device: POST /storePreset
        ↓
User presses PRESET_N button
        ↓
Device GETs: {oct_url}/core02/svc-bmx-adapter-orion/prod/orion/station?data={base64}
        ↓
OCT decodes base64 → converts HTTPS→HTTP → returns BmxPlaybackResponse
        ↓
Device plays stream ✅
```

## What Does NOT Work

- ❌ BoseSoundTouchAPI.StorePreset() - silently fails
- ❌ TuneIn source - device returns 500
- ❌ HTTPS streams directly - device LED turns orange
- ❌ HTTP 302 redirect to HTTPS - device fails

---
Tested: 2026-02-22
Author: OCT Development
"""

import base64
import json

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from opencloudtouch.devices.adapter import BoseDeviceClientAdapter
from opencloudtouch.core.exceptions import DeviceConnectionError


class TestStorePresetDirectHTTP:
    """Tests for direct HTTP POST to /storePreset endpoint.

    Critical: BoseSoundTouchAPI library's StorePreset() silently fails.
    We MUST use direct httpx POST to the device's /storePreset endpoint.
    """

    @pytest.fixture
    def mock_soundtouch_device(self):
        """Mock SoundTouchDevice for testing."""
        mock = MagicMock()
        mock.Device.DeviceName = "Test Kitchen"
        mock.SupportedUris = MagicMock()
        mock.SupportedUris.Uri = []
        return mock

    @pytest.fixture
    def adapter(self, mock_soundtouch_device):
        """Create BoseDeviceClientAdapter with mocked SoundTouch device."""
        with patch(
            "opencloudtouch.devices.adapter.SoundTouchDevice",
            return_value=mock_soundtouch_device,
        ):
            return BoseDeviceClientAdapter("http://192.168.178.79:8090")

    @pytest.mark.asyncio
    async def test_store_preset_builds_correct_xml_payload(self, adapter):
        """Test that store_preset builds correct XML payload with LOCAL_INTERNET_RADIO."""
        # Arrange
        captured_request = {}

        async def mock_post(url, content, headers):
            captured_request["url"] = url
            captured_request["content"] = content
            captured_request["headers"] = headers
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            await adapter.store_preset(
                device_id="689E194F7D2F",
                preset_number=3,
                station_url="http://stream.example.com/radio.mp3",
                station_name="Test Radio",
                oct_backend_url="http://192.168.178.108:7777",
                station_image_url="http://example.com/logo.png",
            )

        # Assert - URL is correct
        assert captured_request["url"] == "http://192.168.178.79:8090/storePreset"

        # Assert - Content-Type is XML
        assert captured_request["headers"]["Content-Type"] == "application/xml"

        # Assert - XML contains LOCAL_INTERNET_RADIO source
        xml_content = captured_request["content"]
        assert 'source="LOCAL_INTERNET_RADIO"' in xml_content
        assert '<preset id="3"' in xml_content
        assert "<itemName>Test Radio</itemName>" in xml_content
        assert "core02/svc-bmx-adapter-orion/prod/orion/station" in xml_content

    @pytest.mark.asyncio
    async def test_store_preset_encodes_stream_data_as_base64(self, adapter):
        """Test that stream data is properly base64-encoded in the location URL."""
        captured_request = {}

        async def mock_post(url, content, headers):
            captured_request["content"] = content
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            await adapter.store_preset(
                device_id="689E194F7D2F",
                preset_number=5,
                station_url="http://stream.example.com/radio.mp3",
                station_name="My Station",
                oct_backend_url="http://localhost:7777",
                station_image_url="http://example.com/logo.png",
            )

        # Extract base64 data from XML
        xml_content = captured_request["content"]
        # Find the data= parameter in location URL
        import re

        match = re.search(r"data=([A-Za-z0-9_-]+={0,2})", xml_content)
        assert match, "Base64 data parameter not found in location URL"

        # Decode and verify
        base64_data = match.group(1)
        decoded_json = base64.urlsafe_b64decode(base64_data).decode()
        decoded_data = json.loads(decoded_json)

        assert decoded_data["streamUrl"] == "http://stream.example.com/radio.mp3"
        assert decoded_data["name"] == "My Station"
        assert decoded_data["imageUrl"] == "http://example.com/logo.png"

    @pytest.mark.asyncio
    async def test_store_preset_validates_preset_number_range(self, adapter):
        """Test that preset number must be between 1-6."""
        # Act & Assert - preset 0 is invalid
        with pytest.raises(ValueError) as exc_info:
            await adapter.store_preset(
                device_id="689E194F7D2F",
                preset_number=0,
                station_url="http://stream.example.com/radio.mp3",
                station_name="Test",
                oct_backend_url="http://localhost:7777",
            )
        assert "1-6" in str(exc_info.value)

        # Act & Assert - preset 7 is invalid
        with pytest.raises(ValueError) as exc_info:
            await adapter.store_preset(
                device_id="689E194F7D2F",
                preset_number=7,
                station_url="http://stream.example.com/radio.mp3",
                station_name="Test",
                oct_backend_url="http://localhost:7777",
            )
        assert "1-6" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_preset_handles_http_error(self, adapter):
        """Test error handling when device returns HTTP error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(DeviceConnectionError) as exc_info:
                await adapter.store_preset(
                    device_id="689E194F7D2F",
                    preset_number=1,
                    station_url="http://stream.example.com/radio.mp3",
                    station_name="Test",
                    oct_backend_url="http://localhost:7777",
                )
            assert "HTTP 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_preset_handles_connection_error(self, adapter):
        """Test error handling when device is unreachable."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(DeviceConnectionError) as exc_info:
                await adapter.store_preset(
                    device_id="689E194F7D2F",
                    preset_number=1,
                    station_url="http://stream.example.com/radio.mp3",
                    station_name="Test",
                    oct_backend_url="http://localhost:7777",
                )
            assert "Connection refused" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_preset_all_six_presets(self, adapter):
        """Test that all preset numbers 1-6 are valid."""
        for preset_num in range(1, 7):
            captured_request = {}

            async def mock_post(url, content, headers):
                captured_request["content"] = content
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                return mock_response

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = mock_post
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_class.return_value = mock_client

                # Act - should not raise
                await adapter.store_preset(
                    device_id="689E194F7D2F",
                    preset_number=preset_num,
                    station_url="http://stream.example.com/radio.mp3",
                    station_name=f"Station {preset_num}",
                    oct_backend_url="http://localhost:7777",
                )

            # Assert - correct preset ID in XML
            assert f'<preset id="{preset_num}"' in captured_request["content"]

    @pytest.mark.asyncio
    async def test_store_preset_special_characters_in_name(self, adapter):
        """Test that station names with special characters are handled."""
        captured_request = {}

        async def mock_post(url, content, headers):
            captured_request["content"] = content
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act - German Umlauts and special chars
            await adapter.store_preset(
                device_id="689E194F7D2F",
                preset_number=1,
                station_url="http://stream.example.com/radio.mp3",
                station_name="MDR SPUTNIK – Café Müller",
                oct_backend_url="http://localhost:7777",
            )

        # Assert - Name is in the XML
        assert "MDR SPUTNIK – Café Müller" in captured_request["content"]

    @pytest.mark.asyncio
    async def test_store_preset_empty_image_url(self, adapter):
        """Test that empty image URL is handled correctly."""
        captured_request = {}

        async def mock_post(url, content, headers):
            captured_request["content"] = content
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act - no image URL
            await adapter.store_preset(
                device_id="689E194F7D2F",
                preset_number=1,
                station_url="http://stream.example.com/radio.mp3",
                station_name="Test Station",
                oct_backend_url="http://localhost:7777",
                station_image_url="",  # Empty
            )

        # Extract and decode base64 data
        import re

        match = re.search(r"data=([A-Za-z0-9_-]+={0,2})", captured_request["content"])
        base64_data = match.group(1)
        decoded_data = json.loads(base64.urlsafe_b64decode(base64_data).decode())

        assert decoded_data["imageUrl"] == ""


class TestStorePresetXMLFormat:
    """Tests for the exact XML format expected by Bose devices."""

    @pytest.fixture
    def mock_soundtouch_device(self):
        """Mock SoundTouchDevice."""
        mock = MagicMock()
        mock.Device.DeviceName = "Test Device"
        mock.SupportedUris = MagicMock()
        mock.SupportedUris.Uri = []
        return mock

    @pytest.fixture
    def adapter(self, mock_soundtouch_device):
        """Create adapter with mocked device."""
        with patch(
            "opencloudtouch.devices.adapter.SoundTouchDevice",
            return_value=mock_soundtouch_device,
        ):
            return BoseDeviceClientAdapter("http://192.168.178.79:8090")

    @pytest.mark.asyncio
    async def test_xml_has_correct_structure(self, adapter):
        """Test that XML has the exact structure expected by Bose firmware."""
        captured_request = {}

        async def mock_post(url, content, headers):
            captured_request["content"] = content
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await adapter.store_preset(
                device_id="689E194F7D2F",
                preset_number=4,
                station_url="http://stream.radio.de/live.mp3",
                station_name="Radio Example",
                oct_backend_url="http://192.168.178.108:7777",
            )

        xml = captured_request["content"]

        # Verify XML structure
        assert xml.startswith("<preset ")
        assert "</preset>" in xml
        assert '<ContentItem source="LOCAL_INTERNET_RADIO"' in xml
        assert 'type="stationurl"' in xml
        assert 'isPresetable="true"' in xml
        assert "<itemName>Radio Example</itemName>" in xml
        assert (
            'location="http://192.168.178.108:7777/core02/svc-bmx-adapter-orion' in xml
        )

    @pytest.mark.asyncio
    async def test_xml_attributes_createdOn_updatedOn(self, adapter):
        """Test that preset has createdOn and updatedOn attributes."""
        captured_request = {}

        async def mock_post(url, content, headers):
            captured_request["content"] = content
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await adapter.store_preset(
                device_id="689E194F7D2F",
                preset_number=1,
                station_url="http://stream.example.com/radio.mp3",
                station_name="Test",
                oct_backend_url="http://localhost:7777",
            )

        xml = captured_request["content"]
        assert 'createdOn="0"' in xml
        assert 'updatedOn="0"' in xml


class TestOrionAdapterBase64RoundTrip:
    """Tests for base64 encoding/decoding roundtrip with Orion adapter."""

    def test_base64_roundtrip_simple(self):
        """Test simple base64 encode/decode roundtrip."""
        # This is what store_preset does
        stream_data = {
            "streamUrl": "http://stream.example.com/radio.mp3",
            "name": "Test Radio",
            "imageUrl": "http://example.com/logo.png",
        }
        json_str = json.dumps(stream_data)
        base64_data = base64.urlsafe_b64encode(json_str.encode()).decode()

        # This is what the Orion adapter does
        decoded_str = base64.urlsafe_b64decode(base64_data).decode()
        decoded_data = json.loads(decoded_str)

        assert decoded_data == stream_data

    def test_base64_roundtrip_german_umlauts(self):
        """Test base64 roundtrip with German umlauts."""
        stream_data = {
            "streamUrl": "http://stream.example.com/radio.mp3",
            "name": "SWR3 – Größter Spaß im Südwesten",
            "imageUrl": "",
        }
        json_str = json.dumps(stream_data)
        base64_data = base64.urlsafe_b64encode(json_str.encode()).decode()

        decoded_str = base64.urlsafe_b64decode(base64_data).decode()
        decoded_data = json.loads(decoded_str)

        assert decoded_data["name"] == "SWR3 – Größter Spaß im Südwesten"

    def test_base64_url_safe_characters(self):
        """Test that base64 uses URL-safe encoding (no + or /)."""
        stream_data = {
            "streamUrl": "http://stream.example.com/radio.mp3",
            "name": "Test",
            "imageUrl": "",
        }
        json_str = json.dumps(stream_data)
        base64_data = base64.urlsafe_b64encode(json_str.encode()).decode()

        # URL-safe base64 uses - and _ instead of + and /
        assert "+" not in base64_data
        assert "/" not in base64_data


class TestWhyLibraryFails:
    """Documentation tests explaining why BoseSoundTouchAPI library fails.

    **CRITICAL**: These tests document the library bug we discovered on 2026-02-22.
    The BoseSoundTouchAPI library's StorePreset() method does NOT work correctly.

    Symptoms:
    - Library logs "Stored preset successfully"
    - Device's /presets endpoint still shows OLD data
    - UI shows success but preset doesn't work

    Root cause: Unknown library implementation issue
    Solution: Use direct httpx POST to /storePreset endpoint
    """

    def test_documentation_library_fails_silently(self):
        """Document that BoseSoundTouchAPI.StorePreset silently fails.

        This test exists purely for documentation. The actual behavior is:

        ```python
        # This looks like it works but DOESN'T:
        from bosesoundtouchapi import SoundTouchDevice
        device = SoundTouchDevice("192.168.178.79")
        preset = Preset(...)
        device.StorePreset(preset)  # Returns without error but doesn't work!

        # This is what actually works:
        import httpx
        xml = '<preset id="1">...</preset>'
        httpx.post(f"http://{ip}:8090/storePreset", content=xml)  # ✅ Works!
        ```
        """
        # This test always passes - it's documentation
        assert True, "See docstring for explanation of library bug"

    def test_documentation_direct_http_works(self):
        """Document that direct HTTP POST to /storePreset works.

        **Working XML format:**
        ```xml
        <preset id="3" createdOn="0" updatedOn="0">
            <ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl"
                location="http://oct-server:7777/core02/svc-bmx-adapter-orion/prod/orion/station?data={base64}"
                sourceAccount="" isPresetable="true">
                <itemName>Station Name</itemName>
            </ContentItem>
        </preset>
        ```

        **Request:**
        ```
        POST /storePreset HTTP/1.1
        Host: 192.168.178.79:8090
        Content-Type: application/xml

        {xml payload}
        ```
        """
        assert True, "See docstring for working XML format"
