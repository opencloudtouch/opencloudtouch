"""Tests for WebSocket connection pool manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.devices.websocket.connection import ConnectionState
from opencloudtouch.devices.websocket.manager import WebSocketManager, _STAGGER_DELAY


@pytest.fixture
def on_event():
    return AsyncMock()


@pytest.fixture
def on_state_change():
    return AsyncMock()


@pytest.fixture
def manager(on_event, on_state_change):
    return WebSocketManager(on_event=on_event, on_state_change=on_state_change)


@pytest.fixture
def devices():
    return [
        {"device_id": "AAA", "ip": "192.168.1.10"},
        {"device_id": "BBB", "ip": "192.168.1.11"},
        {"device_id": "CCC", "ip": "192.168.1.12"},
    ]


class TestWebSocketManagerStart:
    @pytest.mark.asyncio
    async def test_start_creates_connections(self, manager, devices):
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_instance = AsyncMock()
            mock_instance.connect = AsyncMock()
            MockWS.return_value = mock_instance

            await manager.start(devices)

            assert len(manager.device_ids) == 3
            assert MockWS.call_count == 3
            assert mock_instance.connect.call_count == 3

    @pytest.mark.asyncio
    async def test_start_staggered(self, manager, devices):
        """Connections should be staggered with delays."""
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with (
            patch("opencloudtouch.devices.websocket.manager.DeviceWebSocket") as MockWS,
            patch(
                "opencloudtouch.devices.websocket.manager.asyncio.sleep",
                side_effect=mock_sleep,
            ),
        ):
            mock_instance = AsyncMock()
            mock_instance.connect = AsyncMock()
            MockWS.return_value = mock_instance

            await manager.start(devices)

        # 3 devices → 2 stagger delays (no delay after last)
        assert len(sleep_calls) == 2
        assert all(d == _STAGGER_DELAY for d in sleep_calls)

    @pytest.mark.asyncio
    async def test_start_skips_existing(self, manager):
        """Already managed devices should be skipped."""
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_instance = AsyncMock()
            mock_instance.connect = AsyncMock()
            MockWS.return_value = mock_instance

            devices = [{"device_id": "AAA", "ip": "192.168.1.10"}]
            await manager.start(devices)
            await manager.start(devices)  # Second call

            # Should only create one connection
            assert MockWS.call_count == 1


class TestWebSocketManagerStop:
    @pytest.mark.asyncio
    async def test_stop_disconnects_all(self, manager, devices):
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_instance = AsyncMock()
            mock_instance.connect = AsyncMock()
            mock_instance.disconnect = AsyncMock()
            MockWS.return_value = mock_instance

            await manager.start(devices)
            await manager.stop()

            assert mock_instance.disconnect.call_count == 3
            assert len(manager.device_ids) == 0


class TestWebSocketManagerIndividual:
    @pytest.mark.asyncio
    async def test_connect_device(self, manager):
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_instance = AsyncMock()
            mock_instance.connect = AsyncMock()
            MockWS.return_value = mock_instance

            await manager.connect_device("NEW", "10.0.0.1")

            assert "NEW" in manager.device_ids
            mock_instance.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_device(self, manager):
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_instance = AsyncMock()
            mock_instance.connect = AsyncMock()
            mock_instance.disconnect = AsyncMock()
            MockWS.return_value = mock_instance

            await manager.connect_device("DEV1", "10.0.0.1")
            await manager.disconnect_device("DEV1")

            assert "DEV1" not in manager.device_ids
            mock_instance.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self, manager):
        """Disconnecting unknown device should not raise."""
        await manager.disconnect_device("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_reconnect_device(self, manager):
        """Reconnect should disconnect then connect with new IP."""
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_instances = [AsyncMock(), AsyncMock()]
            for m in mock_instances:
                m.connect = AsyncMock()
                m.disconnect = AsyncMock()
            MockWS.side_effect = mock_instances

            await manager.connect_device("DEV1", "10.0.0.1")
            await manager.reconnect_device("DEV1", "10.0.0.2")

            # First instance disconnected
            mock_instances[0].disconnect.assert_called_once()
            # Second instance created with new IP and connected
            assert "DEV1" in manager.device_ids
            mock_instances[1].connect.assert_called_once()


class TestWebSocketManagerStatus:
    @pytest.mark.asyncio
    async def test_get_status(self, manager):
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_instance = MagicMock()
            mock_instance.connect = AsyncMock()
            mock_instance.state = ConnectionState.CONNECTED
            MockWS.return_value = mock_instance

            await manager.connect_device("DEV1", "10.0.0.1")
            status = manager.get_status()

            assert status == {"DEV1": ConnectionState.CONNECTED}

    @pytest.mark.asyncio
    async def test_get_status_empty(self, manager):
        assert manager.get_status() == {}
