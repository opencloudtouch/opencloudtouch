"""Radio station data models."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RadioStation:
    """
    Unified Radio Station model across all providers.

    Providers map their specific response formats to this model.
    """

    station_id: str  # Provider-specific ID
    name: str
    url: str
    country: str
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    tags: Optional[List[str]] = None
    favicon: Optional[str] = None
    homepage: Optional[str] = None
    provider: str = "unknown"  # e.g. "radiobrowser", "tunein"
