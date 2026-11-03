"""Tests for switching the input source of a device (Bluetooth, AUX, AirPlay)."""

from unittest.mock import MagicMock, patch

import pytest

from opencloudtouch.devices.mock_client import MockDeviceClient


@pytest.mark.asyncio
class TestMockSelectSource:
    @pytest.mark.parametrize("source", ["BLUETOOTH", "AUX", "AIRPLAY"])
    async def test_selectable_sources_are_accepted(self, source):
        await MockDeviceClient(device_id="AABBCC112233").select_source(source)

    @pytest.mark.parametrize("source", ["SPOTIFY", "INTERNET_RADIO", "bluetooth", ""])
    async def test_other_sources_are_rejected(self, source):
        client = MockDeviceClient(device_id="AABBCC112233")
        with pytest.raises(ValueError):
            await client.select_source(source)


@pytest.mark.asyncio
class TestAdapterSelectSource:
    async def _client(self):
        from opencloudtouch.devices.adapter import BoseDeviceClientAdapter

        with patch("opencloudtouch.devices.client_adapter.SoundTouchDevice"):
            with patch("opencloudtouch.devices.client_adapter.BoseClient") as bose:
                instance = MagicMock()
                bose.return_value = instance
                return BoseDeviceClientAdapter("http://192.168.1.100:8090"), instance

    async def test_aux_is_selected_with_its_source_account(self):
        client, instance = await self._client()
        await client.select_source("AUX")
        instance.SelectSource.assert_called_once_with("AUX", "AUX")

    async def test_bluetooth_is_selected_without_account(self):
        client, instance = await self._client()
        await client.select_source("BLUETOOTH")
        instance.SelectSource.assert_called_once_with("BLUETOOTH", None)

    async def test_invalid_source_is_rejected_before_any_request(self):
        client, instance = await self._client()
        with pytest.raises(ValueError):
            await client.select_source("SPOTIFY")
        instance.SelectSource.assert_not_called()

    async def test_device_errors_become_connection_errors(self):
        from opencloudtouch.core.exceptions import DeviceConnectionError

        client, instance = await self._client()
        instance.SelectSource.side_effect = RuntimeError("boom")
        with pytest.raises(DeviceConnectionError):
            await client.select_source("AIRPLAY")
