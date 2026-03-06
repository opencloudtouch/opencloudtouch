"""Unit tests for SettingsRepository.

Covers CRUD operations for manual IP addresses.
"""

import pytest

from opencloudtouch.settings.repository import SettingsRepository


@pytest.fixture
async def settings_repo():
    """Create an in-memory SettingsRepository, close it after each test.

    Closing is mandatory: aiosqlite.Connection extends Thread (non-daemon).
    Without close(), the background thread blocks Python from exiting.
    """
    repo = SettingsRepository(":memory:")
    await repo.initialize()
    yield repo
    await repo.close()


class TestSettingsRepositoryManualIps:
    """Tests for manual IP address CRUD in SettingsRepository."""

    @pytest.mark.asyncio
    async def test_get_manual_ips_empty(self, settings_repo):
        """Fresh repository returns empty list."""
        result = await settings_repo.get_manual_ips()

        assert result == []

    @pytest.mark.asyncio
    async def test_set_and_get_manual_ips(self, settings_repo):
        """set_manual_ips stores IPs, get_manual_ips retrieves them (covers 102-114)."""
        await settings_repo.set_manual_ips(["192.168.1.100", "192.168.1.101"])
        result = await settings_repo.get_manual_ips()

        assert result == ["192.168.1.100", "192.168.1.101"]

    @pytest.mark.asyncio
    async def test_set_manual_ips_replaces_existing(self, settings_repo):
        """Calling set_manual_ips again replaces the previous list."""
        await settings_repo.set_manual_ips(["10.0.0.1", "10.0.0.2"])
        await settings_repo.set_manual_ips(["192.168.2.1"])
        result = await settings_repo.get_manual_ips()

        assert result == ["192.168.2.1"]
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_set_manual_ips_empty_list_clears_all(self, settings_repo):
        """Setting an empty list removes all stored IPs."""
        await settings_repo.set_manual_ips(["10.0.0.1"])
        await settings_repo.set_manual_ips([])
        result = await settings_repo.get_manual_ips()

        assert result == []
