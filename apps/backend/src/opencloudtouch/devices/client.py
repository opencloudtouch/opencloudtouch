"""
Device HTTP Client Interface
Abstract base for device communication
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceInfo:
    """Device information from /info endpoint."""

    device_id: str
    name: str
    type: str  # Device model/type identifier
    mac_address: str
    ip_address: str
    firmware_version: str
    module_type: Optional[str] = None
    variant: Optional[str] = None
    variant_mode: Optional[str] = None


@dataclass
class NowPlayingInfo:
    """Information about currently playing content."""

    source: str  # e.g., "INTERNET_RADIO", "BLUETOOTH", "AUX"
    state: str  # "PLAY_STATE", "PAUSE_STATE", "STOP_STATE"
    station_name: Optional[str] = None
    artist: Optional[str] = None
    track: Optional[str] = None
    album: Optional[str] = None
    artwork_url: Optional[str] = None


class DeviceClient(ABC):
    """Abstract client for device HTTP API."""

    @abstractmethod
    async def get_info(self) -> DeviceInfo:
        """
        Get device information from /info endpoint.

        Returns:
            DeviceInfo object with device details

        Raises:
            ConnectionError: If device is unreachable
            ValueError: If response cannot be parsed
        """
        pass

    @abstractmethod
    async def get_now_playing(self) -> NowPlayingInfo:
        """
        Get current playback status from /now_playing endpoint.

        Returns:
            NowPlayingInfo object with playback details

        Raises:
            ConnectionError: If device is unreachable
            ValueError: If response cannot be parsed
        """
        pass

    @abstractmethod
    async def press_key(self, key: str, state: str = "both") -> None:
        """
        Simulate a key press on the device.

        Args:
            key: Key name (e.g., "PRESET_1", "PRESET_2", ...)
            state: Key state ("press", "release", or "both")

        Raises:
            ConnectionError: If device is unreachable
            ValueError: If key or state is invalid
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close client connections."""
        pass

    @abstractmethod
    async def store_preset(
        self,
        device_id: str,
        preset_number: int,
        station_url: str,
        station_name: str,
        oct_backend_url: str,
        station_image_url: str = "",
    ) -> None:
        """
        Store a preset on the Bose device.

        Args:
            device_id: Bose device identifier
            preset_number: Preset slot (1-6)
            station_url: RadioBrowser stream URL
            station_name: Station display name
            oct_backend_url: OCT backend base URL
            station_image_url: Optional station logo URL
        """
        pass
