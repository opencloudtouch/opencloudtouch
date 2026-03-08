"""Device discovery implementations"""

from opencloudtouch.devices.discovery.manual import ManualDiscovery
from opencloudtouch.devices.discovery.ssdp import SSDPDiscovery

__all__ = ["SSDPDiscovery", "ManualDiscovery"]
