"""WebSocket client for real-time device event streaming."""

from opencloudtouch.devices.websocket.connection import ConnectionState, DeviceWebSocket
from opencloudtouch.devices.websocket.manager import WebSocketManager
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType, parse_event

__all__ = [
    "ConnectionState",
    "DeviceEvent",
    "DeviceWebSocket",
    "EventType",
    "WebSocketManager",
    "parse_event",
]
