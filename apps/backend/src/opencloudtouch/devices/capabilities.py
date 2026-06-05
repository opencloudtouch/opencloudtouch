"""
Device capability detection module.

This module provides capability detection for streaming devices to enable
model-specific features in the UI and graceful degradation when endpoints
are not supported.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional, Set

from bosesoundtouchapi import (  # type: ignore[import-untyped]
    SoundTouchClient,
    SoundTouchError,
)

logger = logging.getLogger(__name__)


@dataclass
class DeviceCapabilities:
    """Device capabilities for feature detection."""

    device_id: str
    device_type: str

    # Hardware capabilities
    has_hdmi_control: bool = False
    has_bass_control: bool = False
    has_balance_control: bool = False
    has_audio_product_level_control: bool = False
    has_audio_product_tone_control: bool = False

    # Network capabilities
    has_bluetooth: bool = False
    has_aux_input: bool = False

    # Zone/Group capabilities
    has_zone_support: bool = False
    has_group_support: bool = False

    # Supported sources
    supported_sources: List[str] = field(default_factory=list)

    # All supported endpoints
    supported_endpoints: Set[str] = field(default_factory=set)

    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.supported_sources is None:
            self.supported_sources = []
        if self.supported_endpoints is None:
            self.supported_endpoints = set()

    def supports_endpoint(self, endpoint: str) -> bool:
        """Check if device supports a specific endpoint."""
        # Remove leading slash if present
        endpoint = endpoint.lstrip("/")
        return endpoint in self.supported_endpoints

    def supports_source(self, source: str) -> bool:
        """Check if device supports a specific source."""
        return source.upper() in [s.upper() for s in self.supported_sources]

    def is_soundbar(self) -> bool:
        """Check if device is a soundbar (ST300)."""
        return "300" in self.device_type

    def is_wireless_speaker(self) -> bool:
        """Check if device is a wireless speaker (ST30, ST10, etc.)."""
        return not self.is_soundbar()


async def get_device_capabilities(client: SoundTouchClient) -> DeviceCapabilities:
    """
    Get comprehensive device capabilities from /capabilities and /supportedURLs.

    Args:
        client: Device client instance (from bosesoundtouchapi library)

    Returns:
        DeviceCapabilities object with all detected capabilities

    Raises:
        SoundTouchError: If device communication fails
    """
    logger.debug("Fetching capabilities", extra={"device": client.Device.DeviceName})

    # Run all three blocking bosesoundtouchapi calls concurrently in the thread
    # pool so the asyncio event loop is never blocked by synchronous HTTP I/O.
    info, caps, sources_response = await asyncio.gather(
        asyncio.to_thread(client.GetInformation),
        asyncio.to_thread(client.GetCapabilities),
        asyncio.to_thread(client.GetSourceList),
    )

    # Parse supported endpoints from supportedURLs
    supported_endpoints = set()
    for url_obj in caps.SupportedUrls:
        # url_obj is SupportedUrl with Url property
        endpoint = url_obj.Url.lstrip("/")
        supported_endpoints.add(endpoint)

    # Parse available sources
    supported_sources = [
        source.Source for source in sources_response.Sources if source.Status == "READY"
    ]

    # Build capabilities object
    capabilities = DeviceCapabilities(
        device_id=info.DeviceId,
        device_type=info.DeviceType,
        # Hardware capabilities from /capabilities
        has_hdmi_control=caps.IsProductCECHDMIControlCapable,
        has_bass_control=caps.IsBassCapable,
        has_audio_product_level_control=caps.IsAudioProductLevelControlCapable,
        has_audio_product_tone_control=(
            caps.IsAudioProductToneControlsCapable
            if hasattr(caps, "IsAudioProductToneControlsCapable")
            else False
        ),
        # Network capabilities - check if endpoints exist
        has_bluetooth="bluetoothInfo" in supported_endpoints,
        has_aux_input="AUX" in [s.upper() for s in supported_sources],
        # Zone/Group capabilities
        has_zone_support="getZone" in supported_endpoints
        or "setZone" in supported_endpoints,
        has_group_support="getGroup" in supported_endpoints,
        # Supported sources and endpoints
        supported_sources=supported_sources,
        supported_endpoints=supported_endpoints,
    )

    logger.info(
        "Device capabilities detected",
        extra={
            "device_id": capabilities.device_id,
            "device_type": capabilities.device_type,
            "has_hdmi": capabilities.has_hdmi_control,
            "has_bass": capabilities.has_bass_control,
            "source_count": len(capabilities.supported_sources),
            "endpoint_count": len(capabilities.supported_endpoints),
        },
    )

    return capabilities


async def get_capabilities_for_ip(ip: str) -> DeviceCapabilities:
    """Get device capabilities by IP address.

    Convenience wrapper that handles SoundTouchDevice and SoundTouchClient
    construction internally, keeping the bosesoundtouchapi dependency
    encapsulated within this module.

    Args:
        ip: Device IP address

    Returns:
        DeviceCapabilities with all detected capabilities

    Raises:
        SoundTouchError: If device communication fails
    """
    from bosesoundtouchapi import SoundTouchDevice  # noqa: PLC0415

    st_device = SoundTouchDevice(ip)
    client = SoundTouchClient(st_device)
    return await get_device_capabilities(client)


async def safe_api_call(
    client: SoundTouchClient, endpoint_uri, endpoint_name: Optional[str] = None
):
    """
    Make API call with graceful error handling.

    Args:
        client: Device client instance (from bosesoundtouchapi library)
        endpoint_uri: SoundTouchUri object (e.g., SoundTouchNodes.volume)
        endpoint_name: Optional human-readable endpoint name for logging

    Returns:
        API response or None if endpoint not supported

    Raises:
        SoundTouchError: Only for unexpected errors (not 404, 401)
    """
    endpoint_name = endpoint_name or endpoint_uri.Path

    try:
        return client.Get(endpoint_uri)

    except SoundTouchError as e:
        if e.ErrorCode == 404:
            logger.info(
                "Endpoint not supported on device",
                extra={
                    "device": client.Device.DeviceName,
                    "endpoint": endpoint_name,
                    "error_code": 404,
                },
            )
            return None

        elif e.ErrorCode == 401:
            logger.warning(
                "Authentication required for endpoint",
                extra={
                    "device": client.Device.DeviceName,
                    "endpoint": endpoint_name,
                    "error_code": 401,
                },
            )
            return None

        # Re-raise unexpected errors
        logger.error(
            "Unexpected error calling endpoint",
            extra={
                "device": client.Device.DeviceName,
                "endpoint": endpoint_name,
                "error_code": e.ErrorCode,
                "error_name": e.Name,
            },
        )
        raise


def get_feature_flags_for_ui(capabilities: DeviceCapabilities) -> dict[str, Any]:
    """
    Convert DeviceCapabilities to UI feature flags.

    This determines which UI controls should be shown/hidden based on
    device capabilities.

    Args:
        capabilities: DeviceCapabilities object

    Returns:
        Dictionary of feature flags for frontend
    """
    return {
        "device_id": capabilities.device_id,
        "device_type": capabilities.device_type,
        "is_soundbar": capabilities.is_soundbar(),
        "features": {
            # Audio controls
            "hdmi_control": capabilities.has_hdmi_control,
            "bass_control": capabilities.has_bass_control,
            "balance_control": capabilities.has_balance_control,
            "advanced_audio": capabilities.has_audio_product_level_control,
            "tone_controls": capabilities.has_audio_product_tone_control,
            # Input sources
            "bluetooth": capabilities.has_bluetooth,
            "aux_input": capabilities.has_aux_input,
            # Multi-room
            "zone_support": capabilities.has_zone_support,
            "group_support": capabilities.has_group_support,
        },
        "sources": capabilities.supported_sources,
        # Endpoint availability for advanced features
        "advanced": {
            "introspect": capabilities.supports_endpoint("introspect"),
            "navigate": capabilities.supports_endpoint("navigate"),
            "search": capabilities.supports_endpoint("search"),
        },
    }
