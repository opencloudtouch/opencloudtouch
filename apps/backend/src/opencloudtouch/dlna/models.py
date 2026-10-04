"""Models for DLNA media servers and browse results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DlnaServer:
    """A discovered DLNA/UPnP media server."""

    id: str
    name: str
    location: str
    control_url: str


@dataclass(frozen=True)
class DlnaItem:
    """A DLNA ContentDirectory item or container."""

    id: str
    parent_id: str
    title: str
    is_container: bool

    resource_url: str | None = None
    media_class: str | None = None

    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    creator: str | None = None
    album_art_url: str | None = None

    duration: str | None = None
    size: int | None = None
    bitrate: int | None = None
    sample_frequency: int | None = None
    audio_channels: int | None = None
    protocol_info: str | None = None
