"""Devices Domain - All device-related functionality"""

from opencloudtouch.devices.adapter import (
    BoseDeviceClientAdapter,
    BoseDeviceDiscoveryAdapter,
)
from opencloudtouch.devices.capabilities import (
    get_device_capabilities,
    get_feature_flags_for_ui,
)
from opencloudtouch.devices.client import DeviceClient, DeviceInfo, NowPlayingInfo
from opencloudtouch.devices.repository import Device, DeviceRepository

__all__ = [
    "BoseDeviceDiscoveryAdapter",
    "BoseDeviceClientAdapter",
    "Device",
    "DeviceRepository",
    "DeviceClient",
    "DeviceInfo",
    "NowPlayingInfo",
    "get_device_capabilities",
    "get_feature_flags_for_ui",
]
