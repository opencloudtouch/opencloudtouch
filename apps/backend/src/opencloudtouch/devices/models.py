"""Data models for device management.

Contains domain models that are shared across multiple modules.
Separates data structures from business logic and persistence.
"""

from dataclasses import dataclass


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
