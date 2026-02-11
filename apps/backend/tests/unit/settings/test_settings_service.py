"""Unit tests for SettingsService.

Tests business logic layer for settings management.
Following TDD Red-Green-Refactor cycle.
"""

import pytest
from unittest.mock import AsyncMock

from opencloudtouch.settings.service import SettingsService


@pytest.fixture
def mock_repository():
    """Mock SettingsRepository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def settings_service(mock_repository):
    """SettingsService instance with mocked repository."""
    return SettingsService(repository=mock_repository)


class TestSettingsServiceManualIPs:
    """Test manual IP management."""

    @pytest.mark.asyncio
    async def test_get_manual_ips_success(self, settings_service, mock_repository):
        """Test getting all manual IPs."""
        # Arrange
        mock_repository.get_manual_ips.return_value = [
            "192.168.1.100",
            "192.168.1.101",
        ]

        # Act
        result = await settings_service.get_manual_ips()

        # Assert
        assert len(result) == 2
        assert "192.168.1.100" in result
        assert "192.168.1.101" in result
        mock_repository.get_manual_ips.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_manual_ips_empty(self, settings_service, mock_repository):
        """Test getting manual IPs when none configured."""
        # Arrange
        mock_repository.get_manual_ips.return_value = []

        # Act
        result = await settings_service.get_manual_ips()

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_add_manual_ip_valid(self, settings_service, mock_repository):
        """Test adding a valid manual IP."""
        # Arrange
        valid_ip = "192.168.1.100"
        mock_repository.add_manual_ip.return_value = None

        # Act
        await settings_service.add_manual_ip(valid_ip)

        # Assert
        mock_repository.add_manual_ip.assert_called_once_with(valid_ip)

    @pytest.mark.asyncio
    async def test_add_manual_ip_invalid_format(
        self, settings_service, mock_repository
    ):
        """Test adding IP with invalid format."""
        # Arrange
        invalid_ips = [
            "192.168.1",  # Missing octet
            "192.168.1.256",  # Invalid octet (>255)
            "192.168.1.-1",  # Negative octet
            "192.168.1.abc",  # Non-numeric
            "not.an.ip.address",  # Invalid
            "",  # Empty
        ]

        # Act & Assert
        for invalid_ip in invalid_ips:
            with pytest.raises(ValueError, match="Invalid IP address"):
                await settings_service.add_manual_ip(invalid_ip)

        # Assert repository was never called
        mock_repository.add_manual_ip.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_manual_ip_success(self, settings_service, mock_repository):
        """Test removing a manual IP."""
        # Arrange
        ip_to_remove = "192.168.1.100"
        mock_repository.remove_manual_ip.return_value = None

        # Act
        await settings_service.remove_manual_ip(ip_to_remove)

        # Assert
        mock_repository.remove_manual_ip.assert_called_once_with(ip_to_remove)

    @pytest.mark.asyncio
    async def test_set_manual_ips_success(self, settings_service, mock_repository):
        """Test setting all manual IPs (replace operation)."""
        # Arrange
        new_ips = ["192.168.1.100", "192.168.1.101", "192.168.1.102"]
        existing_ips = ["192.168.1.50", "192.168.1.51"]

        mock_repository.get_manual_ips.return_value = existing_ips
        mock_repository.remove_manual_ip.return_value = None
        mock_repository.add_manual_ip.return_value = None

        # Act
        result = await settings_service.set_manual_ips(new_ips)

        # Assert
        assert result == new_ips

        # Verify old IPs were removed
        assert mock_repository.remove_manual_ip.call_count == len(existing_ips)

        # Verify new IPs were added
        assert mock_repository.add_manual_ip.call_count == len(new_ips)

    @pytest.mark.asyncio
    async def test_set_manual_ips_validates_all_before_changes(
        self, settings_service, mock_repository
    ):
        """Test that all IPs are validated before any changes are made."""
        # Arrange
        mixed_ips = ["192.168.1.100", "INVALID", "192.168.1.101"]
        mock_repository.get_manual_ips.return_value = []

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid IP address"):
            await settings_service.set_manual_ips(mixed_ips)

        # Assert no repository changes were made
        mock_repository.remove_manual_ip.assert_not_called()
        mock_repository.add_manual_ip.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_manual_ips_with_duplicates(
        self, settings_service, mock_repository
    ):
        """Test setting manual IPs with duplicates (should deduplicate)."""
        # Arrange
        ips_with_duplicates = ["192.168.1.100", "192.168.1.101", "192.168.1.100"]
        mock_repository.get_manual_ips.return_value = []
        mock_repository.add_manual_ip.return_value = None

        # Act
        result = await settings_service.set_manual_ips(ips_with_duplicates)

        # Assert - duplicates should be removed
        assert len(result) == 2
        assert "192.168.1.100" in result
        assert "192.168.1.101" in result

        # Should only add unique IPs
        assert mock_repository.add_manual_ip.call_count == 2


class TestSettingsServiceIPValidation:
    """Test IP address validation logic."""

    @pytest.mark.asyncio
    async def test_validate_ip_valid_addresses(self, settings_service):
        """Test validation accepts valid IP addresses."""
        valid_ips = [
            "0.0.0.0",
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "255.255.255.255",
        ]

        # Act & Assert - should not raise
        for ip in valid_ips:
            settings_service._validate_ip(ip)  # Should not raise

    @pytest.mark.asyncio
    async def test_validate_ip_invalid_addresses(self, settings_service):
        """Test validation rejects invalid IP addresses."""
        invalid_ips = [
            "256.1.1.1",  # Octet > 255
            "1.1.1",  # Missing octet
            "1.1.1.1.1",  # Too many octets
            "abc.def.ghi.jkl",  # Non-numeric
            "192.168.-1.1",  # Negative
            "",  # Empty
            "   ",  # Whitespace only
        ]

        # Act & Assert
        for ip in invalid_ips:
            with pytest.raises(ValueError, match="Invalid IP address"):
                settings_service._validate_ip(ip)
