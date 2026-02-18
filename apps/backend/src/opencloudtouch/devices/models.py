"""Data models for device management.

Contains domain models that are shared across multiple modules.
Separates data structures from business logic and persistence.
"""

from dataclasses import dataclass
from enum import Enum

from bosesoundtouchapi import SoundTouchKeys


@dataclass
class SyncResult:
    """Result of device synchronization operation."""

    discovered: int  # Number of devices discovered
    synced: int  # Number of devices successfully synced
    failed: int  # Number of devices that failed to sync

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "discovered": self.discovered,
            "synced": self.synced,
            "failed": self.failed,
        }


class KeyType(str, Enum):
    """Logical key types exposed by OCT."""

    PLAY = "PLAY"
    PAUSE = "PAUSE"
    STOP = "STOP"
    NEXT_TRACK = "NEXT_TRACK"
    PREV_TRACK = "PREV_TRACK"
    POWER = "POWER"
    MUTE = "MUTE"


KEY_MAPPING: dict[KeyType, SoundTouchKeys] = {
    KeyType.PLAY: SoundTouchKeys.PLAY,
    KeyType.PAUSE: SoundTouchKeys.PAUSE,
    KeyType.STOP: SoundTouchKeys.STOP,
    KeyType.NEXT_TRACK: SoundTouchKeys.NEXT_TRACK,
    KeyType.PREV_TRACK: SoundTouchKeys.PREV_TRACK,
    KeyType.POWER: SoundTouchKeys.POWER,
    KeyType.MUTE: SoundTouchKeys.MUTE,
}
