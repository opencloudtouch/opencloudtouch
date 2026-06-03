"""WebSocket connection pool manager for all devices.

Manages WebSocket connections to multiple SoundTouch devices with
staggered startup and individual device lifecycle control.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from opencloudtouch.core.config import get_config
from opencloudtouch.devices.websocket.connection import ConnectionState, DeviceWebSocket
from opencloudtouch.devices.websocket.parser import DeviceEvent

logger = logging.getLogger(__name__)

# Stagger delay between device connections to avoid network burst
_STAGGER_DELAY: float = 0.2  # 200ms


class WebSocketManager:
    """Manages WebSocket connections to all known devices.

    Args:
        on_event: Async callback invoked for every parsed device event.
        on_state_change: Async callback for connection state transitions.
    """

    def __init__(
        self,
        on_event: Optional[Callable[[DeviceEvent], Awaitable[None]]] = None,
        on_state_change: Optional[
            Callable[[str, ConnectionState], Awaitable[None]]
        ] = None,
    ):
        self._connections: dict[str, DeviceWebSocket] = {}
        self._on_event = on_event
        self._on_state_change = on_state_change

    @property
    def device_ids(self) -> list[str]:
        """List of managed device IDs."""
        return list(self._connections.keys())

    async def start(self, devices: list[dict[str, str]]) -> None:
        """Connect to all devices with staggered startup.

        Args:
            devices: List of dicts with 'device_id' and 'ip' keys.
        """
        config = get_config()
        port = config.device_ws_port

        for i, device in enumerate(devices):
            device_id = device["device_id"]
            ip = device["ip"]

            if device_id in self._connections:
                logger.debug("Device %s already managed, skipping", device_id)
                continue

            ws = DeviceWebSocket(
                device_id=device_id,
                ip=ip,
                port=port,
                on_event=self._on_event,
                on_state_change=self._on_state_change,
            )
            self._connections[device_id] = ws
            ws.connect()

            # Stagger between connections (except after last device)
            if i < len(devices) - 1:
                await asyncio.sleep(_STAGGER_DELAY)

        logger.info(
            "ws.manager.started for %d device(s)",
            len(self._connections),
            extra={"device_count": len(self._connections)},
        )

    async def stop(self) -> None:
        """Disconnect all devices and clean up."""
        tasks = [ws.disconnect() for ws in self._connections.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._connections.clear()
        logger.info("ws.manager.stopped")

    def connect_device(self, device_id: str, ip: str) -> None:
        """Connect to a single device.

        Args:
            device_id: Device identifier.
            ip: Device IP address.
        """
        if device_id in self._connections:
            logger.debug("Device %s already managed", device_id)
            return

        config = get_config()
        ws = DeviceWebSocket(
            device_id=device_id,
            ip=ip,
            port=config.device_ws_port,
            on_event=self._on_event,
            on_state_change=self._on_state_change,
        )
        self._connections[device_id] = ws
        ws.connect()
        logger.info(
            "ws.connected %s at %s",
            device_id,
            ip,
            extra={"device_id": device_id, "ip": ip},
        )

    async def disconnect_device(self, device_id: str) -> None:
        """Disconnect a single device.

        Args:
            device_id: Device identifier to disconnect.
        """
        ws = self._connections.pop(device_id, None)
        if ws:
            await ws.disconnect()
            logger.info(
                "ws.disconnected %s",
                device_id,
                extra={"device_id": device_id},
            )

    async def reconnect_device(self, device_id: str, new_ip: str) -> None:
        """Reconnect a device with a new IP address.

        Args:
            device_id: Device identifier.
            new_ip: New IP address for the device.
        """
        await self.disconnect_device(device_id)
        self.connect_device(device_id, new_ip)
        logger.info(
            "ws.reconnected %s at %s",
            device_id,
            new_ip,
            extra={"device_id": device_id, "ip": new_ip},
        )

    async def ensure_connection(self, device_id: str, ip: str) -> None:
        """Ensure device is connected at the given IP.

        If the device is already connected at the same IP, this is a no-op.
        If the IP changed, reconnects. If the device is new, connects.
        """
        existing = self._connections.get(device_id)
        if existing is None:
            self.connect_device(device_id, ip)
            return
        if existing.ip != ip:
            logger.info(
                "ws.ip_changed %s %s → %s",
                device_id,
                existing.ip,
                ip,
                extra={"device_id": device_id, "old_ip": existing.ip, "new_ip": ip},
            )
            await self.reconnect_device(device_id, ip)

    def get_status(self) -> dict[str, ConnectionState]:
        """Get connection state for all managed devices.

        Returns:
            Dict mapping device_id to ConnectionState.
        """
        return {device_id: ws.state for device_id, ws in self._connections.items()}

    def get_health(self) -> dict:
        """Get detailed health info for all managed connections."""
        connections = {
            device_id: ws.health_info() for device_id, ws in self._connections.items()
        }
        total_connected = sum(
            1 for info in connections.values() if info["state"] == "connected"
        )
        return {
            "connections": connections,
            "total_connected": total_connected,
            "total_devices": len(connections),
        }
