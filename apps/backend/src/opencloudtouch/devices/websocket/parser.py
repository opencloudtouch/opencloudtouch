"""XML event parser for SoundTouch WebSocket messages.

Parses XML events pushed by Bose SoundTouch devices over WebSocket
and converts them to typed Python dataclasses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as ET

from opencloudtouch.devices.client import NowPlayingInfo, VolumeInfo

if TYPE_CHECKING:
    from opencloudtouch.devices.websocket.connection import ConnectionState

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """WebSocket event types pushed by SoundTouch devices."""

    NOW_PLAYING = "now_playing"
    VOLUME = "volume"
    PRESETS = "presets"
    ZONE = "zone"
    CONNECTION = "connection"
    BASS = "bass"
    METADATA_ENRICHED = "metadata_enriched"
    UNKNOWN = "unknown"


# Map XML element tag → EventType
_TAG_MAP: dict[str, EventType] = {
    "nowPlayingUpdated": EventType.NOW_PLAYING,
    "volumeUpdated": EventType.VOLUME,
    "presetsUpdated": EventType.PRESETS,
    "zoneUpdated": EventType.ZONE,
    "connectionStateUpdated": EventType.CONNECTION,
    "bassUpdated": EventType.BASS,
    "recentsUpdated": EventType.PRESETS,
}

# Root elements that are not <updates> but known and harmless
_IGNORED_ROOT_ELEMENTS = frozenset({"SoundTouchSdkInfo", "userActivityUpdate"})


@dataclass
class DeviceEvent:
    """Parsed device WebSocket event."""

    device_id: str
    event_type: EventType
    now_playing: Optional[NowPlayingInfo] = None
    volume: Optional[VolumeInfo] = None
    connection_state: Optional[ConnectionState] = None
    raw_xml: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def parse_event(xml_string: str) -> DeviceEvent | None:
    """Parse a WebSocket XML message into a DeviceEvent.

    Args:
        xml_string: Raw XML string from WebSocket.

    Returns:
        Parsed DeviceEvent or None if parsing fails.
    """
    if not xml_string or not xml_string.strip():
        logger.debug("Empty XML message received")
        return None

    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError:
        logger.warning("Malformed XML received: %.200s", xml_string)
        return None

    if root.tag != "updates":
        if root.tag in _IGNORED_ROOT_ELEMENTS:
            logger.debug("Ignoring known non-event element: %s", root.tag)
        else:
            logger.warning("Unexpected root element: %s", root.tag)
        return None

    device_id = root.get("deviceID", "")
    if not device_id:
        logger.warning("Missing deviceID in updates element")
        return None

    # Find first child element to determine event type
    child = next(iter(root), None)
    if child is None:
        logger.debug("Empty <updates> element for device %s", device_id)
        return DeviceEvent(
            device_id=device_id,
            event_type=EventType.UNKNOWN,
            raw_xml=xml_string,
        )

    event_type = _TAG_MAP.get(child.tag, EventType.UNKNOWN)
    if event_type == EventType.UNKNOWN:
        logger.debug("Device %s unknown event tag: %s", device_id, child.tag)

    event = DeviceEvent(
        device_id=device_id,
        event_type=event_type,
        raw_xml=xml_string,
    )

    if event_type == EventType.NOW_PLAYING:
        event.now_playing = _parse_now_playing(child)
        logger.debug(
            "Device %s parsed now_playing: source=%s state=%s station=%s artist=%s track=%s art=%s",
            device_id,
            event.now_playing.source,
            event.now_playing.state,
            event.now_playing.station_name,
            event.now_playing.artist,
            event.now_playing.track,
            bool(event.now_playing.artwork_url),
        )
    elif event_type == EventType.VOLUME:
        event.volume = _parse_volume(child)
        logger.debug(
            "Device %s parsed volume: actual=%s target=%s muted=%s",
            device_id,
            event.volume.actual,
            event.volume.target,
            event.volume.muted,
        )
    else:
        logger.debug("Device %s parsed event: %s", device_id, event_type.value)

    return event


def _parse_now_playing(element: Element) -> NowPlayingInfo:
    """Parse nowPlayingUpdated element into NowPlayingInfo.

    Args:
        element: The <nowPlayingUpdated> XML element.

    Returns:
        NowPlayingInfo with parsed fields.
    """
    # The actual data is nested: <nowPlayingUpdated><nowPlaying source="...">...</nowPlaying>
    np = element.find("nowPlaying")
    if np is None:
        return NowPlayingInfo(source="UNKNOWN", state="STOP_STATE")

    source = np.get("source", "UNKNOWN")

    def _text(tag: str) -> str | None:
        el = np.find(tag)
        return el.text if el is not None and el.text else None

    state = _text("playStatus") or "STOP_STATE"
    artwork_url = None
    art_el = np.find("art")
    if art_el is not None and art_el.text:
        artwork_url = art_el.text

    return NowPlayingInfo(
        source=source,
        state=state,
        station_name=_text("stationName"),
        artist=_text("artist"),
        track=_text("track"),
        album=_text("album"),
        artwork_url=artwork_url,
    )


def _parse_volume(element: Element) -> VolumeInfo:
    """Parse volumeUpdated element into VolumeInfo.

    Args:
        element: The <volumeUpdated> XML element.

    Returns:
        VolumeInfo with parsed fields.
    """
    vol = element.find("volume")
    if vol is None:
        return VolumeInfo(actual=0, target=0, muted=False)

    def _int(tag: str, default: int = 0) -> int:
        el = vol.find(tag)
        if el is not None and el.text:
            try:
                return int(el.text)
            except ValueError:
                pass
        return default

    mute_el = vol.find("muteenabled")
    muted = (
        mute_el is not None
        and mute_el.text is not None
        and mute_el.text.lower() == "true"
    )

    return VolumeInfo(
        actual=_int("actualvolume"),
        target=_int("targetvolume"),
        muted=muted,
    )
