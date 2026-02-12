"""
Radio Provider Factory.

Factory pattern for Mock vs Real RadioBrowser provider selection.
Based on OCT_MOCK_MODE environment variable.
"""

import logging
import os

from opencloudtouch.radio.provider import RadioProvider

logger = logging.getLogger(__name__)


def get_radio_adapter() -> RadioProvider:
    """
    Factory function: Select Mock or Real radio provider.

    Returns:
        RadioProvider: MockRadioAdapter if OCT_MOCK_MODE=true, else RadioBrowserAdapter

    Decision Flow:
        1. Check OCT_MOCK_MODE env var
        2. Return MockRadioAdapter (deterministic) or RadioBrowserAdapter (real API)

    Examples:
        >>> # In production
        >>> provider = get_radio_adapter()
        >>> stations = await provider.search_by_name("BBC")

        >>> # In tests (with OCT_MOCK_MODE=true)
        >>> provider = get_radio_adapter()  # Returns MockRadioAdapter
        >>> stations = await provider.search_by_name("BBC")  # 20 mock stations
    """
    mock_mode = os.getenv("OCT_MOCK_MODE", "false").lower() == "true"

    if mock_mode:
        logger.info("[FACTORY] Creating MockRadioAdapter (OCT_MOCK_MODE=true)")
        from opencloudtouch.radio.providers.mock import MockRadioAdapter

        return MockRadioAdapter()

    logger.info("[FACTORY] Creating RadioBrowserAdapter (OCT_MOCK_MODE=false)")
    from opencloudtouch.radio.providers.radiobrowser import RadioBrowserAdapter

    return RadioBrowserAdapter()
