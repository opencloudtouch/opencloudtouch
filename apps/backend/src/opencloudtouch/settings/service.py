"""Settings service - Business logic layer for settings management.

Manages application settings including manual device IP addresses.
Separates HTTP layer (routes) from business logic from data layer (repository).
"""

import logging
import re
from typing import List

from opencloudtouch.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

# IP address validation regex (xxx.xxx.xxx.xxx where xxx = 0-255)
IP_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)


class SettingsService:
    """Service for managing application settings.

    This service provides business logic for settings operations,
    ensuring separation between HTTP layer (routes) and data layer (repository).

    Responsibilities:
    - Validate IP addresses
    - Manage manual device IP addresses
    - Orchestrate transactional operations (set_manual_ips)
    """

    def __init__(self, repository: SettingsRepository):
        """Initialize settings service.

        Args:
            repository: SettingsRepository for data persistence
        """
        self.repository = repository

    def _validate_ip(self, ip: str) -> None:
        """Validate IP address format.

        Args:
            ip: IP address to validate

        Raises:
            ValueError: If IP address is invalid
        """
        if not ip or not ip.strip():
            raise ValueError("Invalid IP address: empty string")

        if not IP_PATTERN.match(ip):
            raise ValueError(f"Invalid IP address: {ip}")

    async def get_manual_ips(self) -> List[str]:
        """Get all manual device IP addresses.

        Returns:
            List of manually configured IP addresses
        """
        return await self.repository.get_manual_ips()

    async def add_manual_ip(self, ip: str) -> None:
        """Add a manual device IP address.

        Validates IP format before adding.

        Args:
            ip: IP address to add

        Raises:
            ValueError: If IP address is invalid
        """
        # Validate IP format
        self._validate_ip(ip)

        logger.info(f"Adding manual device IP: {ip}")

        await self.repository.add_manual_ip(ip)

    async def remove_manual_ip(self, ip: str) -> None:
        """Remove a manual device IP address.

        Args:
            ip: IP address to remove
        """
        logger.info(f"Removing manual device IP: {ip}")

        await self.repository.remove_manual_ip(ip)

    async def set_manual_ips(self, ips: List[str]) -> List[str]:
        """Set all manual device IP addresses (replace operation).

        Replaces existing manual IPs with new list.
        Validates all IPs before making any changes (transactional).

        Args:
            ips: List of IP addresses to set

        Returns:
            List of IP addresses after deduplication

        Raises:
            ValueError: If any IP address is invalid (no changes made)
        """
        # Deduplicate
        unique_ips = list(dict.fromkeys(ips))  # Preserves order

        # Validate ALL IPs before making any changes
        for ip in unique_ips:
            self._validate_ip(ip)

        logger.info(
            f"Setting manual IPs: {len(unique_ips)} unique IPs "
            f"(from {len(ips)} provided)"
        )

        # Get existing IPs
        existing_ips = await self.repository.get_manual_ips()

        # Remove all existing IPs
        for ip in existing_ips:
            await self.repository.remove_manual_ip(ip)

        # Add new IPs
        for ip in unique_ips:
            await self.repository.add_manual_ip(ip)

        logger.info(f"Manual IPs updated: {unique_ips}")

        return unique_ips
