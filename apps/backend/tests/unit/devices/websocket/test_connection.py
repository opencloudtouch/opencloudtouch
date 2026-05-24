"""Tests for single device WebSocket connection."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.devices.websocket.connection import (
    ConnectionState,
    DeviceWebSocket,
    _BACKOFF_BASE,
    _BACKOFF_MAX,
)
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType


@pytest.fixture
def on_event():
    return AsyncMock()


@pytest.fixture
def on_state_change():
    return AsyncMock()


@pytest.fixture
def device_ws(on_event, on_state_change):
    return DeviceWebSocket(
        device_id="AABBCCDDEEFF",
        ip="192.168.1.10",
        port=8080,
        on_event=on_event,
        on_state_change=on_state_change,
    )


class TestDeviceWebSocketInit:
    def test_initial_state(self, device_ws):
        assert device_ws.state == ConnectionState.DISCONNECTED
        assert device_ws.device_id == "AABBCCDDEEFF"
        assert device_ws.ip == "192.168.1.10"
        assert device_ws.port == 8080

    def test_uri(self, device_ws):
        assert device_ws.uri == "ws://192.168.1.10:8080/"


class TestDeviceWebSocketConnect:
    @pytest.mark.asyncio
    async def test_connect_creates_task(self, device_ws):
        """connect() should create a background task."""
        with patch(
            "opencloudtouch.devices.websocket.connection.ws_connect",
            side_effect=asyncio.CancelledError,
        ):
            await device_ws.connect()
            assert device_ws._listen_task is not None
            assert device_ws._should_run is True
            # Clean up
            await device_ws.disconnect()

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, device_ws):
        """Calling connect() twice should not create duplicate tasks."""
        with patch(
            "opencloudtouch.devices.websocket.connection.ws_connect",
            side_effect=asyncio.CancelledError,
        ):
            await device_ws.connect()
            task1 = device_ws._listen_task
            await device_ws.connect()
            task2 = device_ws._listen_task
            assert task1 is task2
            await device_ws.disconnect()


class TestDeviceWebSocketDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_cleans_up(self, device_ws, on_state_change):
        """disconnect() should cancel task and set state."""
        with patch(
            "opencloudtouch.devices.websocket.connection.ws_connect",
            side_effect=asyncio.CancelledError,
        ):
            await device_ws.connect()
            await device_ws.disconnect()

        assert device_ws._listen_task is None
        assert device_ws._ws is None
        assert device_ws.state == ConnectionState.DISCONNECTED


class TestDeviceWebSocketListenLoop:
    @pytest.mark.asyncio
    async def test_receives_and_dispatches_events(self, on_event, on_state_change):
        """Listen loop should parse messages and call on_event."""
        volume_xml = '<updates deviceID="AA"><volumeUpdated deviceID="AA"><volume><targetvolume>50</targetvolume><actualvolume>50</actualvolume><muteenabled>false</muteenabled></volume></volumeUpdated></updates>'

        mock_ws = AsyncMock()

        async def async_iter():
            yield volume_xml

        mock_ws.__aiter__ = lambda self: async_iter()

        ws = DeviceWebSocket(
            device_id="AA",
            ip="1.2.3.4",
            on_event=on_event,
            on_state_change=on_state_change,
        )
        ws._ws = mock_ws
        ws._should_run = True

        await ws._listen_loop()

        on_event.assert_called_once()
        event = on_event.call_args[0][0]
        assert isinstance(event, DeviceEvent)
        assert event.event_type == EventType.VOLUME
        assert event.volume.target == 50

    @pytest.mark.asyncio
    async def test_skips_unparseable_messages(self, on_event, on_state_change):
        """Malformed XML should be skipped, not raise."""
        mock_ws = AsyncMock()

        async def async_iter():
            yield "<garbage>"

        mock_ws.__aiter__ = lambda self: async_iter()

        ws = DeviceWebSocket(
            device_id="AA",
            ip="1.2.3.4",
            on_event=on_event,
            on_state_change=on_state_change,
        )
        ws._ws = mock_ws
        ws._should_run = True

        await ws._listen_loop()
        on_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_bytes_messages(self, on_event, on_state_change):
        """Bytes messages should be decoded to UTF-8."""
        xml = b'<updates deviceID="BB"><bassUpdated deviceID="BB"><bass><targetbass>0</targetbass><actualbass>0</actualbass></bass></bassUpdated></updates>'

        mock_ws = AsyncMock()

        async def async_iter():
            yield xml

        mock_ws.__aiter__ = lambda self: async_iter()

        ws = DeviceWebSocket(
            device_id="BB",
            ip="1.2.3.4",
            on_event=on_event,
            on_state_change=on_state_change,
        )
        ws._ws = mock_ws
        ws._should_run = True

        await ws._listen_loop()
        on_event.assert_called_once()


class TestDeviceWebSocketReconnect:
    @pytest.mark.asyncio
    async def test_invalid_handshake_marks_failed(self, on_state_change):
        """InvalidHandshake should set state to FAILED and stop retrying."""
        from websockets.exceptions import InvalidHandshake

        with patch(
            "opencloudtouch.devices.websocket.connection.ws_connect",
            side_effect=InvalidHandshake("rejected"),
        ):
            ws = DeviceWebSocket(
                device_id="FF",
                ip="1.2.3.4",
                on_state_change=on_state_change,
            )
            ws._should_run = True
            await ws._connection_loop()

        assert ws.state == ConnectionState.FAILED

    @pytest.mark.asyncio
    async def test_backoff_increases(self, device_ws):
        """Backoff delay should increase exponentially."""
        delays = []

        async def capture_sleep(seconds):
            delays.append(seconds)
            # Don't actually sleep, just raise to stop the loop
            device_ws._should_run = False

        with patch(
            "opencloudtouch.devices.websocket.connection.asyncio.sleep",
            side_effect=capture_sleep,
        ):
            device_ws._should_run = True
            device_ws._backoff_attempt = 0
            await device_ws._reconnect_delay()

        assert len(delays) == 1
        # First attempt: base (1.0) + jitter (0-1)
        assert _BACKOFF_BASE <= delays[0] <= _BACKOFF_BASE + 1.0

    @pytest.mark.asyncio
    async def test_backoff_capped(self, device_ws):
        """Backoff should cap at _BACKOFF_MAX."""
        delays = []

        async def capture_sleep(seconds):
            delays.append(seconds)
            device_ws._should_run = False

        with patch(
            "opencloudtouch.devices.websocket.connection.asyncio.sleep",
            side_effect=capture_sleep,
        ):
            device_ws._should_run = True
            device_ws._backoff_attempt = 100  # Way past cap
            await device_ws._reconnect_delay()

        assert len(delays) == 1
        # Should be capped at _BACKOFF_MAX + jitter
        assert delays[0] <= _BACKOFF_MAX + 1.0


class TestDeviceWebSocketStateCallbacks:
    @pytest.mark.asyncio
    async def test_state_change_callback(self, device_ws, on_state_change):
        """State changes should invoke the callback."""
        await device_ws._set_state(ConnectionState.CONNECTING)
        on_state_change.assert_called_with("AABBCCDDEEFF", ConnectionState.CONNECTING)

    @pytest.mark.asyncio
    async def test_no_callback_on_same_state(self, device_ws, on_state_change):
        """Same state transition should not invoke callback."""
        await device_ws._set_state(ConnectionState.DISCONNECTED)  # Already disconnected
        on_state_change.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_exception_caught(self, device_ws):
        """Exception in state change callback should be caught."""
        failing_cb = AsyncMock(side_effect=RuntimeError("boom"))
        device_ws._on_state_change = failing_cb
        # Should not raise
        await device_ws._set_state(ConnectionState.CONNECTING)
