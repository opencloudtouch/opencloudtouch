"""Tests for WebSocket connection pool manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.devices.websocket.connection import ConnectionState
from opencloudtouch.devices.websocket.manager import _STAGGER_DELAY, WebSocketManager


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

            manager.connect_device("NEW", "10.0.0.1")

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

            manager.connect_device("DEV1", "10.0.0.1")
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

            manager.connect_device("DEV1", "10.0.0.1")
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

            manager.connect_device("DEV1", "10.0.0.1")
            status = manager.get_status()

            assert status == {"DEV1": ConnectionState.CONNECTED}

    @pytest.mark.asyncio
    async def test_get_status_empty(self, manager):
        assert manager.get_status() == {}

    @pytest.mark.asyncio
    async def test_get_health(self, manager):
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock1 = MagicMock()
            mock1.connect = AsyncMock()
            mock1.health_info.return_value = {
                "state": "connected",
                "uptime_s": 120,
                "events_received": 42,
            }
            mock2 = MagicMock()
            mock2.connect = AsyncMock()
            mock2.health_info.return_value = {
                "state": "reconnecting",
                "attempt": 3,
                "events_received": 10,
            }
            MockWS.side_effect = [mock1, mock2]

            manager.connect_device("DEV1", "10.0.0.1")
            manager.connect_device("DEV2", "10.0.0.2")
            health = manager.get_health()

            assert health["total_connected"] == 1
            assert health["total_devices"] == 2
            assert health["connections"]["DEV1"]["state"] == "connected"
            assert health["connections"]["DEV2"]["attempt"] == 3

    @pytest.mark.asyncio
    async def test_get_health_empty(self, manager):
        health = manager.get_health()
        assert health == {"connections": {}, "total_connected": 0, "total_devices": 0}


class TestWebSocketManagerEnsureConnection:
    @pytest.mark.asyncio
    async def test_ensure_new_device_connects(self, manager):
        """ensure_connection for unknown device creates new connection."""
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_instance = MagicMock()
            mock_instance.connect = AsyncMock()
            MockWS.return_value = mock_instance

            await manager.ensure_connection("DEV1", "10.0.0.1")
            assert "DEV1" in manager.device_ids
            mock_instance.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_same_ip_is_noop(self, manager):
        """ensure_connection with same IP does nothing."""
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_instance = MagicMock()
            mock_instance.connect = AsyncMock()
            mock_instance.disconnect = AsyncMock()
            mock_instance.ip = "10.0.0.1"
            MockWS.return_value = mock_instance

            manager.connect_device("DEV1", "10.0.0.1")
            assert MockWS.call_count == 1

            await manager.ensure_connection("DEV1", "10.0.0.1")
            # No new connection created
            assert MockWS.call_count == 1

    @pytest.mark.asyncio
    async def test_ensure_changed_ip_reconnects(self, manager):
        """ensure_connection with different IP triggers reconnect."""
        with patch(
            "opencloudtouch.devices.websocket.manager.DeviceWebSocket"
        ) as MockWS:
            mock_old = MagicMock()
            mock_old.connect = AsyncMock()
            mock_old.disconnect = AsyncMock()
            mock_old.ip = "10.0.0.1"

            mock_new = MagicMock()
            mock_new.connect = AsyncMock()
            mock_new.ip = "10.0.0.99"

            MockWS.side_effect = [mock_old, mock_new]

            manager.connect_device("DEV1", "10.0.0.1")
            await manager.ensure_connection("DEV1", "10.0.0.99")

            # Old connection disconnected
            mock_old.disconnect.assert_called_once()
            # New connection established
            mock_new.connect.assert_called_once()
