"""Single device WebSocket connection with automatic reconnection.

Manages the lifecycle of a WebSocket connection to one SoundTouch device,
including connect, listen, reconnect with exponential backoff, and disconnect.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from enum import Enum
from typing import Awaitable, Callable, Optional

import websockets
from websockets.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from opencloudtouch.devices.websocket.parser import DeviceEvent, parse_event

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """WebSocket connection lifecycle states."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


# Reconnection backoff constants
_BACKOFF_BASE: float = 1.0
_BACKOFF_MAX: float = 30.0
_JITTER_MAX: float = 1.0


class DeviceWebSocket:
    """WebSocket connection to a single SoundTouch device.

    Args:
        device_id: Unique device identifier (MAC address).
        ip: Device IP address.
        port: WebSocket port (default from config).
        on_event: Async callback for parsed events.
        on_state_change: Async callback for connection state changes.
    """

    def __init__(
        self,
        device_id: str,
        ip: str,
        port: int = 8080,
        on_event: Optional[Callable[[DeviceEvent], Awaitable[None]]] = None,
        on_state_change: Optional[
            Callable[[str, ConnectionState], Awaitable[None]]
        ] = None,
    ):
        self.device_id = device_id
        self.ip = ip
        self.port = port
        self._on_event = on_event
        self._on_state_change = on_state_change
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._state = ConnectionState.DISCONNECTED
        self._should_run = False
        self._backoff_attempt = 0
        self._connected_at: float | None = None
        self._events_received: int = 0

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def uri(self) -> str:
        """WebSocket URI for this device."""
        return f"ws://{self.ip}:{self.port}/"

    def health_info(self) -> dict:
        """Return health/status info for this connection."""
        info: dict = {
            "state": self._state.value,
            "events_received": self._events_received,
        }
        if self._connected_at is not None and self._state == ConnectionState.CONNECTED:
            info["uptime_s"] = round(time.monotonic() - self._connected_at)
        if self._state == ConnectionState.RECONNECTING:
            info["attempt"] = self._backoff_attempt
        return info

    async def _set_state(self, new_state: ConnectionState) -> None:
        """Update state and notify callback."""
        old = self._state
        self._state = new_state
        if old != new_state:
            logger.info(
                "ws.state %s %s → %s",
                self.device_id,
                old.value,
                new_state.value,
                extra={
                    "device_id": self.device_id,
                    "old_state": old.value,
                    "new_state": new_state.value,
                },
            )
            if self._on_state_change:
                try:
                    await self._on_state_change(self.device_id, new_state)
                except Exception:
                    logger.exception(
                        "State change callback failed for device %s", self.device_id
                    )

    def connect(self) -> None:
        """Start WebSocket connection and listen loop."""
        if self._should_run:
            logger.debug("Device %s already connecting/connected", self.device_id)
            return

        self._should_run = True
        self._backoff_attempt = 0
        self._listen_task = asyncio.create_task(
            self._connection_loop(), name=f"ws-{self.device_id}"
        )

    async def disconnect(self) -> None:
        """Stop connection and clean up resources."""
        self._should_run = False

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listen_task

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                logger.debug(
                    "ws.close failed for %s (best-effort)",
                    self.device_id,
                    exc_info=True,
                )
            self._ws = None

        self._listen_task = None
        await self._set_state(ConnectionState.DISCONNECTED)

    async def _connection_loop(self) -> None:
        """Main connection loop with automatic reconnection."""
        while self._should_run:
            try:
                await self._set_state(ConnectionState.CONNECTING)
                self._ws = await ws_connect(
                    self.uri,
                    subprotocols=[websockets.Subprotocol("gabbo")],
                    ping_interval=30,
                    ping_timeout=10,
                )
                await self._set_state(ConnectionState.CONNECTED)
                self._backoff_attempt = 0
                self._connected_at = time.monotonic()

                await self._listen_loop()

            except InvalidHandshake as e:
                logger.exception(
                    "ws.handshake_failed %s: %s",
                    self.device_id,
                    e,
                    extra={"device_id": self.device_id, "error": str(e)},
                )
                await self._set_state(ConnectionState.FAILED)
                return

            except (ConnectionClosed, OSError) as e:
                if not self._should_run:
                    break
                logger.warning(
                    "ws.closed %s: %s — will reconnect",
                    self.device_id,
                    e,
                    extra={"device_id": self.device_id, "error": str(e)},
                )
                await self._reconnect_delay()

            except asyncio.CancelledError:
                raise

            except Exception:
                if not self._should_run:
                    break
                logger.exception(
                    "Unexpected error on device %s WebSocket", self.device_id
                )
                await self._reconnect_delay()

    async def _listen_loop(self) -> None:
        """Receive and process messages until disconnected."""
        if self._ws is None:
            return

        async for message in self._ws:
            if not self._should_run:
                break

            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="replace")

            event = parse_event(message)
            if event is None:
                continue

            self._events_received += 1
            logger.debug(
                "ws.event %s %s",
                self.device_id,
                event.event_type.value,
                extra={
                    "device_id": self.device_id,
                    "event_type": event.event_type.value,
                },
            )

            if self._on_event:
                try:
                    await self._on_event(event)
                except Exception:
                    logger.exception(
                        "Event callback failed for device %s, event %s",
                        self.device_id,
                        event.event_type.value,
                    )

    async def _reconnect_delay(self) -> None:
        """Wait with exponential backoff + jitter before reconnecting."""
        await self._set_state(ConnectionState.RECONNECTING)

        delay = min(_BACKOFF_BASE * (2**self._backoff_attempt), _BACKOFF_MAX)
        jitter = random.uniform(0, _JITTER_MAX)  # noqa: S311
        total = delay + jitter
        self._backoff_attempt += 1

        logger.info(
            "ws.reconnecting %s in %.1fs (attempt %d)",
            self.device_id,
            total,
            self._backoff_attempt,
            extra={
                "device_id": self.device_id,
                "backoff_s": round(total, 1),
                "attempt": self._backoff_attempt,
            },
        )
        await asyncio.sleep(total)
