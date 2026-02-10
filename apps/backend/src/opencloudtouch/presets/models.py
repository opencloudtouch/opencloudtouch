"""Domain models for preset management."""

from datetime import UTC, datetime
from typing import Any, Optional


class Preset:
    """
    Preset model representing a device preset configuration.

    Each device can have up to 6 presets (numbered 1-6).
    Each preset is mapped to a radio station from RadioBrowser.
    """

    def __init__(
        self,
        device_id: str,
        preset_number: int,
        station_uuid: str,
        station_name: str,
        station_url: str,
        station_homepage: Optional[str] = None,
        station_favicon: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        id: Optional[int] = None,
    ):
        """
        Initialize a Preset.

        Args:
            device_id: Device identifier (from devices table)
            preset_number: Preset slot (1-6)
            station_uuid: RadioBrowser station UUID
            station_name: Human-readable station name
            station_url: Stream URL for playback
            station_homepage: Optional station homepage URL
            station_favicon: Optional station favicon URL
            created_at: Creation timestamp
            updated_at: Last update timestamp
            id: Database primary key (optional)

        Raises:
            ValueError: If preset_number not in range 1-6
        """
        if not 1 <= preset_number <= 6:
            raise ValueError(f"Invalid preset_number: {preset_number}. Must be 1-6.")

        self.id = id
        self.device_id = device_id
        self.preset_number = preset_number
        self.station_uuid = station_uuid
        self.station_name = station_name
        self.station_url = station_url
        self.station_homepage = station_homepage
        self.station_favicon = station_favicon
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = updated_at or datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "device_id": self.device_id,
            "preset_number": self.preset_number,
            "station_uuid": self.station_uuid,
            "station_name": self.station_name,
            "station_url": self.station_url,
            "station_homepage": self.station_homepage,
            "station_favicon": self.station_favicon,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"Preset(device_id={self.device_id!r}, "
            f"preset_number={self.preset_number}, "
            f"station_name={self.station_name!r})"
        )
