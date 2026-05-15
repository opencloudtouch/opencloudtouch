"""Unit tests for Settings repository."""

import tempfile
from pathlib import Path

import pytest

from opencloudtouch.core.exceptions import DomainValidationError
from opencloudtouch.settings.repository import SettingsRepository


@pytest.fixture
async def settings_repo():
    """Create a temporary settings repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_settings.db"
        repo = SettingsRepository(db_path)
        await repo.initialize()
        yield repo
        await repo.close()


class TestSettingsRepository:
    """Tests for SettingsRepository."""

    @pytest.mark.asyncio
    async def test_add_manual_ip(self, settings_repo):
        """Test adding a manual IP address."""
        # Arrange
        ip = "192.168.1.10"

        # Act
        await settings_repo.add_manual_ip(ip)

        # Assert
        ips = await settings_repo.get_manual_ips()
        assert ip in ips

    @pytest.mark.asyncio
    async def test_add_multiple_manual_ips(self, settings_repo):
        """Test adding multiple manual IP addresses."""
        # Arrange
        ips_to_add = ["192.168.1.10", "192.168.1.20", "10.0.0.5"]

        # Act
        for ip in ips_to_add:
            await settings_repo.add_manual_ip(ip)

        # Assert
        retrieved_ips = await settings_repo.get_manual_ips()
        assert retrieved_ips == ips_to_add  # Should be in creation order

    @pytest.mark.asyncio
    async def test_remove_manual_ip(self, settings_repo):
        """Test removing a manual IP address."""
        # Arrange
        ip = "192.168.1.10"
        await settings_repo.add_manual_ip(ip)

        # Act
        await settings_repo.remove_manual_ip(ip)

        # Assert
        ips = await settings_repo.get_manual_ips()
        assert ip not in ips

    @pytest.mark.asyncio
    async def test_remove_nonexistent_ip(self, settings_repo):
        """Test removing an IP that doesn't exist (should not raise error)."""
        # Arrange
        ip = "192.168.1.99"

        # Act & Assert (should not raise)
        await settings_repo.remove_manual_ip(ip)

    @pytest.mark.asyncio
    async def test_get_manual_ips_empty(self, settings_repo):
        """Test getting manual IPs when none exist."""
        # Act
        ips = await settings_repo.get_manual_ips()

        # Assert
        assert ips == []

    @pytest.mark.asyncio
    async def test_duplicate_ip_raises_error(self, settings_repo):
        """Test that adding duplicate IP raises ValueError."""
        # Arrange
        ip = "192.168.1.10"
        await settings_repo.add_manual_ip(ip)

        # Act & Assert
        with pytest.raises(DomainValidationError, match="IP address already exists"):
            await settings_repo.add_manual_ip(ip)

    @pytest.mark.asyncio
    async def test_invalid_ip_format_raises_error(self, settings_repo):
        """Test that invalid IP format raises ValueError."""
        # Arrange
        invalid_ips = [
            "256.1.1.1",  # Out of range
            "192.168.1",  # Too few octets
            "192.168.1.1.1",  # Too many octets
            "abc.def.ghi.jkl",  # Non-numeric
            "192.168.-1.1",  # Negative
        ]

        # Act & Assert
        for invalid_ip in invalid_ips:
            with pytest.raises(DomainValidationError, match="Invalid IP address"):
                await settings_repo.add_manual_ip(invalid_ip)

    @pytest.mark.asyncio
    async def test_manual_ips_persist_across_connections(self):
        """Test that manual IPs persist when reopening database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "persist_test.db"
            ip = "192.168.1.10"

            # First connection: Add IP
            repo1 = SettingsRepository(db_path)
            await repo1.initialize()
            await repo1.add_manual_ip(ip)
            await repo1.close()

            # Second connection: Verify IP exists
            repo2 = SettingsRepository(db_path)
            await repo2.initialize()
            ips = await repo2.get_manual_ips()
            await repo2.close()

            # Assert
            assert ip in ips
