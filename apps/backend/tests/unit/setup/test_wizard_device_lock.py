"""Tests for the set-based per-device operation guard in WizardService.

Verifies that concurrent Telnet operations on the same device IP are
rejected with RuntimeError, while operations on different IPs proceed
independently.
"""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.setup.wizard_service import (
    WizardService,
    _device_operations_in_progress,
)


@dataclass
class _FakeConfigResult:
    success: bool = True
    urls_configured: int = 3
    envswitch_applied: bool = True
    errors: list[str] | None = None


@dataclass
class _FakeVerifyResult:
    success: bool = True
    configuration: dict | None = None
    error: str | None = None


@pytest.fixture(autouse=True)
def _clear_tracking_set():
    """Ensure the global tracking set is empty before/after each test."""
    _device_operations_in_progress.clear()
    yield
    _device_operations_in_progress.clear()


class TestDeviceOperationGuard:
    """Verify that the set-based guard rejects concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_configure_same_ip_raises(self):
        """Second configure_telnet_urls call for the same IP raises RuntimeError."""
        service = WizardService()
        blocker = asyncio.Event()

        async def _slow_configure(*_a, **_kw):
            await blocker.wait()
            return _FakeConfigResult()

        with patch(
            "opencloudtouch.setup.telnet_config_service.TelnetConfigService"
        ) as mock_cls:
            instance = mock_cls.return_value
            instance.configure_urls = AsyncMock(side_effect=_slow_configure)

            # Start first (will block on the event)
            first = asyncio.create_task(
                service.configure_telnet_urls("192.168.1.10", "10.0.0.1", 7778)
            )
            # Yield so the first task registers the IP
            await asyncio.sleep(0)

            # Second call for the same IP must raise
            with pytest.raises(RuntimeError, match="already in progress"):
                await service.configure_telnet_urls("192.168.1.10", "10.0.0.1", 7778)

            # Unblock the first task and let it finish cleanly
            blocker.set()
            await first

    @pytest.mark.asyncio
    async def test_concurrent_verify_same_ip_raises(self):
        """Second verify_telnet_config call for the same IP raises RuntimeError."""
        service = WizardService()
        blocker = asyncio.Event()

        async def _slow_verify(*_a, **_kw):
            await blocker.wait()
            return _FakeVerifyResult()

        with patch(
            "opencloudtouch.setup.telnet_config_service.TelnetConfigService"
        ) as mock_cls:
            instance = mock_cls.return_value
            instance.verify_configuration = AsyncMock(side_effect=_slow_verify)

            first = asyncio.create_task(
                service.verify_telnet_config("192.168.1.10")
            )
            await asyncio.sleep(0)

            with pytest.raises(RuntimeError, match="already in progress"):
                await service.verify_telnet_config("192.168.1.10")

            blocker.set()
            await first

    @pytest.mark.asyncio
    async def test_different_ips_run_concurrently(self):
        """Operations on different IPs do NOT block each other."""
        service = WizardService()

        with patch(
            "opencloudtouch.setup.telnet_config_service.TelnetConfigService"
        ) as mock_cls:
            instance = mock_cls.return_value
            instance.configure_urls = AsyncMock(return_value=_FakeConfigResult())

            r1, r2 = await asyncio.gather(
                service.configure_telnet_urls("192.168.1.10", "10.0.0.1", 7778),
                service.configure_telnet_urls("192.168.1.11", "10.0.0.1", 7778),
            )
            assert r1["success"] is True
            assert r2["success"] is True

    @pytest.mark.asyncio
    async def test_ip_removed_after_success(self):
        """IP is removed from tracking set after a successful operation."""
        service = WizardService()

        with patch(
            "opencloudtouch.setup.telnet_config_service.TelnetConfigService"
        ) as mock_cls:
            instance = mock_cls.return_value
            instance.configure_urls = AsyncMock(return_value=_FakeConfigResult())

            await service.configure_telnet_urls("192.168.1.10", "10.0.0.1", 7778)
            assert "192.168.1.10" not in _device_operations_in_progress

    @pytest.mark.asyncio
    async def test_ip_removed_after_failure(self):
        """IP is removed from tracking set even when the operation raises."""
        service = WizardService()

        with patch(
            "opencloudtouch.setup.telnet_config_service.TelnetConfigService"
        ) as mock_cls:
            instance = mock_cls.return_value
            instance.configure_urls = AsyncMock(
                side_effect=ConnectionRefusedError("nope")
            )

            with pytest.raises(ConnectionRefusedError):
                await service.configure_telnet_urls("192.168.1.10", "10.0.0.1", 7778)

            assert "192.168.1.10" not in _device_operations_in_progress
