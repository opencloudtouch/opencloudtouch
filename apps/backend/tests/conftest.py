"""Pytest configuration and fixtures for tests.

Suppress common warnings to keep test output clean.
Provides shared fixtures with optimized scopes for faster parallel execution.
"""

import logging
import sys
import warnings

import pytest
from opencloudtouch.core.config import AppConfig

# Fix Windows asyncio cleanup issues
# The asyncio module logs debug messages during event loop cleanup that
# can fail when pytest closes stdout. Suppress asyncio logging.
if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Suppress asyncio debug logging that causes issues during pytest cleanup
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

# Suppress specific deprecation warnings
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*datetime.datetime.utcnow.*"
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=".*The 'app' shortcut is now deprecated.*",
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*default datetime adapter.*"
)


# Shared fixtures with optimized scopes for parallel execution


@pytest.fixture(scope="session")
def test_config():
    """Shared test configuration (session scope for parallel workers)."""
    return AppConfig(
        host="0.0.0.0",
        port=7777,
        db_path=":memory:",
        log_level="DEBUG",
        discovery_enabled=False,
        discovery_timeout=10,
        manual_device_ips="",
        mock_mode=True,
    )


# Session-scoped mock factories for faster test execution


@pytest.fixture(scope="session")
def mock_repository_factory():
    """Factory for mock DeviceRepository (session scope).

    Returns a new AsyncMock on each call for test isolation.
    """
    from unittest.mock import AsyncMock

    def _create_mock():
        mock = AsyncMock()
        # Pre-configure common methods
        mock.get_all = AsyncMock(return_value=[])
        mock.get_by_device_id = AsyncMock(return_value=None)
        mock.upsert = AsyncMock()
        mock.delete = AsyncMock()
        return mock

    return _create_mock


@pytest.fixture
def mock_repository(mock_repository_factory):
    """Fresh mock DeviceRepository for each test."""
    return mock_repository_factory()


@pytest.fixture(scope="session")
def mock_sync_service_factory():
    """Factory for mock DeviceSyncService (session scope)."""
    from unittest.mock import AsyncMock

    def _create_mock():
        mock = AsyncMock()
        mock.sync_device = AsyncMock()
        return mock

    return _create_mock


@pytest.fixture
def mock_sync_service(mock_sync_service_factory):
    """Fresh mock DeviceSyncService for each test."""
    return mock_sync_service_factory()


@pytest.fixture(scope="session")
def mock_adapter_factory():
    """Factory for mock BoseDeviceDiscoveryAdapter (session scope)."""
    from unittest.mock import AsyncMock

    def _create_mock():
        mock = AsyncMock()
        mock.discover = AsyncMock(return_value=[])
        return mock

    return _create_mock


@pytest.fixture
def mock_adapter(mock_adapter_factory):
    """Fresh mock BoseDeviceDiscoveryAdapter for each test."""
    return mock_adapter_factory()
