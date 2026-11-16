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


@dataclass(frozen=True)
class BrowsePage:
    """One page of browse results.

    ``number_returned`` is what the server reported (before any filtering);
    ``total_matches`` is ``None`` when the server did not report a usable total.
    """

    items: list[DlnaItem]
    number_returned: int
    total_matches: int | None


def is_audio_item(item: DlnaItem) -> bool:
    """Return True for audio items (UPnP class or an ``audio/*`` protocolInfo)."""
    if item.media_class and item.media_class.startswith("object.item.audioItem"):
        return True
    return ":audio/" in (item.protocol_info or "").lower()


def page_cursor(
    page: BrowsePage, starting_index: int, requested_count: int
) -> tuple[int, bool]:
    """Return ``(next_index, has_more)`` for a page, trusting ``number_returned``."""
    next_index = starting_index + page.number_returned
    if page.number_returned <= 0:
        return next_index, False
    if page.total_matches is not None:
        return next_index, next_index < page.total_matches
    return next_index, page.number_returned >= requested_count
