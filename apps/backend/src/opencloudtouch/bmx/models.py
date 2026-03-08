"""Pydantic models for BMX (Bose Media eXchange) API responses.

These models represent the JSON structures expected by SoundTouch devices
when communicating with the BMX service registry and playback endpoints.
"""

from typing import Any

from pydantic import BaseModel, Field


class BmxServiceId(BaseModel):
    """Service identifier."""

    name: str
    value: int


class BmxServiceAssets(BaseModel):
    """Service branding assets."""

    name: str
    description: str = ""
    color: str = "#000000"


class BmxServiceLinks(BaseModel):
    """Service navigation links."""

    bmx_navigate: dict[str, str] = Field(
        default_factory=lambda: {"href": "/v1/navigate"}
    )
    bmx_token: dict[str, str] = Field(default_factory=lambda: {"href": "/v1/token"})
    self: dict[str, str] = Field(default_factory=lambda: {"href": "/"})


class BmxService(BaseModel):
    """Individual BMX service entry."""

    links: BmxServiceLinks = Field(
        default_factory=BmxServiceLinks, serialization_alias="_links"
    )
    id: BmxServiceId
    baseUrl: str
    assets: BmxServiceAssets
    streamTypes: list[str] = ["liveRadio"]
    askAdapter: bool = False
    authenticationModel: dict[str, Any] = Field(
        default_factory=lambda: {
            "anonymousAccount": {"autoCreate": True, "enabled": True}
        }
    )


class BmxServicesResponseLinks(BaseModel):
    """Root-level BMX services links."""

    bmx_services_availability: dict[str, str] = Field(
        default_factory=lambda: {"href": "../servicesAvailability"}
    )


class BmxServicesResponse(BaseModel):
    """BMX registry response."""

    links: BmxServicesResponseLinks = Field(
        default_factory=BmxServicesResponseLinks, serialization_alias="_links"
    )
    askAgainAfter: int = 60000  # 60 seconds in ms (for debugging)
    bmx_services: list[BmxService]


class BmxStream(BaseModel):
    """Audio stream info."""

    hasPlaylist: bool = True
    isRealtime: bool = True
    maxTimeout: int = 60
    bufferingTimeout: int = 20
    connectingTimeout: int = 10
    streamUrl: str
    links: dict[str, Any] = Field(default_factory=dict, serialization_alias="_links")


class BmxAudio(BaseModel):
    """Audio playback info."""

    hasPlaylist: bool = True
    isRealtime: bool = True
    maxTimeout: int = 60
    streamUrl: str
    streams: list[BmxStream] = []


class BmxPlaybackResponse(BaseModel):
    """Playback response with stream URL."""

    audio: BmxAudio
    imageUrl: str = ""
    name: str
    streamType: str = "liveRadio"
    links: dict[str, Any] = Field(default_factory=dict, serialization_alias="_links")
    isFavorite: bool = False
