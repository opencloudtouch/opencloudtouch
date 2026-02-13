"""
Abstract Base Class for Radio Station Providers

This module defines the interface that all radio provider implementations
must follow. Supports RadioBrowser, TuneIn, Music Assistant, etc.
"""

from abc import ABC, abstractmethod
from typing import List

from opencloudtouch.radio.models import RadioStation


class RadioProviderError(Exception):
    """Base exception for radio provider errors."""

    pass


class RadioProviderTimeoutError(RadioProviderError):
    """Raised when provider API times out."""

    pass


class RadioProviderConnectionError(RadioProviderError):
    """Raised when connection to provider fails."""

    pass


class RadioProvider(ABC):
    """
    Abstract base class for radio station providers.

    All concrete implementations (RadioBrowser, TuneIn, etc.)
    must implement these methods.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Unique identifier for this provider.

        Returns:
            str: Provider name (e.g. "radiobrowser", "tunein")
        """
        pass

    @abstractmethod
    async def search_by_name(self, name: str, limit: int = 20) -> List[RadioStation]:
        """
        Search stations by name.

        Args:
            name: Search query (station name or partial match)
            limit: Maximum number of results

        Returns:
            List of RadioStation objects

        Raises:
            RadioProviderError: On provider-specific errors
            RadioProviderTimeoutError: On timeout
            RadioProviderConnectionError: On connection failure
        """
        pass

    @abstractmethod
    async def search_by_country(
        self, country: str, limit: int = 20
    ) -> List[RadioStation]:
        """
        Search stations by country.

        Args:
            country: Country name or code
            limit: Maximum number of results

        Returns:
            List of RadioStation objects

        Raises:
            RadioProviderError: On provider-specific errors
        """
        pass

    @abstractmethod
    async def search_by_tag(self, tag: str, limit: int = 20) -> List[RadioStation]:
        """
        Search stations by genre/tag.

        Args:
            tag: Genre or tag (e.g. "jazz", "rock")
            limit: Maximum number of results

        Returns:
            List of RadioStation objects

        Raises:
            RadioProviderError: On provider-specific errors
        """
        pass

    async def resolve_stream_url(self, station: RadioStation) -> str:
        """
        Resolve final stream URL (optional, override if needed).

        Some providers return playlist URLs (M3U/PLS) that need
        to be resolved to actual stream URLs. Default implementation
        returns station.url unchanged.

        Args:
            station: RadioStation with url to resolve

        Returns:
            Resolved stream URL

        Raises:
            RadioProviderError: On resolution failure
        """
        return station.url
