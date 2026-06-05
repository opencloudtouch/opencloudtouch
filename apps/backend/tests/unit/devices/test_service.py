"""Tests for DeviceService — business logic layer."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.core.exceptions import DeviceNotFoundError, DomainValidationError
from opencloudtouch.db import Device
from opencloudtouch.devices.models import SyncResult
from opencloudtouch.devices.service import DeviceService


def _make_service(repo=None, sync_svc=None, discovery=None) -> DeviceService:
    return DeviceService(
        repository=repo or AsyncMock(),
        sync_service=sync_svc or AsyncMock(),
        discovery_adapter=discovery or AsyncMock(),
    )


def _make_device(device_id="D1", ip="192.168.1.10") -> Device:
    d = MagicMock(spec=Device)
    d.device_id = device_id
    d.ip = ip
    return d


class TestDiscoverDevices:
    @pytest.mark.asyncio
    async def test_returns_discovered_devices(self):
        discovery = AsyncMock()
        discovered = [MagicMock(ip="192.168.1.10", name="Kitchen")]
        discovery.discover.return_value = discovered

        svc = _make_service(discovery=discovery)
        result = await svc.discover_devices(timeout=5)

        assert result == discovered
        discovery.discover.assert_awaited_once_with(timeout=5)


class TestSyncDevices:
    @pytest.mark.asyncio
    async def test_sync_returns_result(self):
        sync_svc = AsyncMock()
        sync_svc.sync.return_value = SyncResult(discovered=2, synced=2, failed=0)

        svc = _make_service(sync_svc=sync_svc)
        result = await svc.sync_devices()

        assert result.synced == 2
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_sync_notifies_ws_callback(self):
        repo = AsyncMock()
        repo.get_all.return_value = [_make_device("D1", "10.0.0.1")]
        sync_svc = AsyncMock()
        sync_svc.sync.return_value = SyncResult(discovered=1, synced=1, failed=0)

        callback = AsyncMock()
        svc = _make_service(repo=repo, sync_svc=sync_svc)
        svc.set_on_device_synced(callback)
        await svc.sync_devices()

        callback.assert_awaited_once_with("D1", "10.0.0.1")

    @pytest.mark.asyncio
    async def test_sync_no_callback_when_not_set(self):
        sync_svc = AsyncMock()
        sync_svc.sync.return_value = SyncResult(discovered=1, synced=1, failed=0)

        svc = _make_service(sync_svc=sync_svc)
        result = await svc.sync_devices()
        assert result.synced == 1


class TestSyncDevicesWithEvents:
    @pytest.mark.asyncio
    async def test_sync_with_events_success(self):
        sync_svc = AsyncMock()
        sync_svc.sync_with_events.return_value = SyncResult(
            discovered=2, synced=2, failed=0
        )
        event_bus = AsyncMock()

        svc = _make_service(sync_svc=sync_svc)
        result = await svc.sync_devices_with_events(event_bus)

        assert result.synced == 2
        assert event_bus.publish.await_count >= 2  # started + completed

    @pytest.mark.asyncio
    async def test_sync_with_events_timeout(self):
        sync_svc = AsyncMock()
        sync_svc.sync_with_events = AsyncMock(side_effect=asyncio.TimeoutError())
        event_bus = AsyncMock()

        svc = _make_service(sync_svc=sync_svc)
        # Patch _SYNC_STREAM_TIMEOUT to something small
        svc._SYNC_STREAM_TIMEOUT = 1
        result = await svc.sync_devices_with_events(event_bus)

        assert result.discovered == 0
        assert result.synced == 0

    @pytest.mark.asyncio
    async def test_sync_with_events_exception(self):
        sync_svc = AsyncMock()
        sync_svc.sync_with_events = AsyncMock(side_effect=RuntimeError("sync failed"))
        event_bus = AsyncMock()

        svc = _make_service(sync_svc=sync_svc)
        with pytest.raises(RuntimeError, match="sync failed"):
            await svc.sync_devices_with_events(event_bus)


class TestNotifyWsForSyncedDevices:
    @pytest.mark.asyncio
    async def test_skips_devices_without_ip(self):
        repo = AsyncMock()
        no_ip_device = _make_device("D2", ip=None)
        repo.get_all.return_value = [no_ip_device]

        callback = AsyncMock()
        svc = _make_service(repo=repo)
        svc.set_on_device_synced(callback)
        await svc._notify_ws_for_synced_devices()

        callback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        repo = AsyncMock()
        repo.get_all.side_effect = RuntimeError("db error")

        callback = AsyncMock()
        svc = _make_service(repo=repo)
        svc.set_on_device_synced(callback)
        await svc._notify_ws_for_synced_devices()  # should not raise


class TestGetDeviceById:
    @pytest.mark.asyncio
    async def test_returns_device(self):
        repo = AsyncMock()
        device = _make_device()
        repo.get_by_device_id.return_value = device

        svc = _make_service(repo=repo)
        result = await svc.get_device_by_id("D1")
        assert result is device

    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self):
        repo = AsyncMock()
        repo.get_by_device_id.return_value = None

        svc = _make_service(repo=repo)
        result = await svc.get_device_by_id("MISSING")
        assert result is None


class TestGetAllDevices:
    @pytest.mark.asyncio
    async def test_returns_all(self):
        repo = AsyncMock()
        devices = [_make_device("D1"), _make_device("D2")]
        repo.get_all.return_value = devices

        svc = _make_service(repo=repo)
        result = await svc.get_all_devices()
        assert len(result) == 2


class TestGetDeviceCapabilities:
    @pytest.mark.asyncio
    async def test_returns_flags(self):
        repo = AsyncMock()
        repo.get_by_device_id.return_value = _make_device()

        svc = _make_service(repo=repo)
        with (
            patch(
                "opencloudtouch.devices.service.get_capabilities_for_ip",
                new_callable=AsyncMock,
                return_value={"hasAux": True},
            ),
            patch(
                "opencloudtouch.devices.service.get_feature_flags_for_ui",
                return_value={"aux": True},
            ),
        ):
            result = await svc.get_device_capabilities("D1")
        assert result == {"aux": True}

    @pytest.mark.asyncio
    async def test_raises_for_unknown_device(self):
        repo = AsyncMock()
        repo.get_by_device_id.return_value = None

        svc = _make_service(repo=repo)
        with pytest.raises(DeviceNotFoundError):
            await svc.get_device_capabilities("MISSING")

    @pytest.mark.asyncio
    async def test_propagates_capability_error(self):
        repo = AsyncMock()
        repo.get_by_device_id.return_value = _make_device()

        svc = _make_service(repo=repo)
        with patch(
            "opencloudtouch.devices.service.get_capabilities_for_ip",
            new_callable=AsyncMock,
            side_effect=ConnectionError("device offline"),
        ):
            with pytest.raises(ConnectionError):
                await svc.get_device_capabilities("D1")


class TestDeleteAllDevices:
    @pytest.mark.asyncio
    async def test_deletes_when_allowed(self):
        repo = AsyncMock()
        svc = _make_service(repo=repo)
        await svc.delete_all_devices(allow_dangerous_operations=True)
        repo.delete_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_when_not_allowed(self):
        svc = _make_service()
        with pytest.raises(PermissionError):
            await svc.delete_all_devices(allow_dangerous_operations=False)


class TestDeleteByDeviceId:
    @pytest.mark.asyncio
    async def test_deletes_device(self):
        repo = AsyncMock()
        svc = _make_service(repo=repo)
        await svc.delete_by_device_id("D1")
        repo.delete_by_device_id.assert_awaited_once_with("D1")


class TestSendKey:
    @pytest.mark.asyncio
    async def test_invalid_key_raises(self):
        repo = AsyncMock()
        repo.get_by_device_id.return_value = _make_device()
        svc = _make_service(repo=repo)

        with pytest.raises(DomainValidationError, match="Unsupported key"):
            await svc.send_key("D1", "INVALID_KEY_XYZ")

    @pytest.mark.asyncio
    async def test_invalid_state_raises(self):
        from opencloudtouch.devices.models import KeyType

        repo = AsyncMock()
        repo.get_by_device_id.return_value = _make_device()
        svc = _make_service(repo=repo)

        first_key = list(KeyType)[0]
        with pytest.raises(DomainValidationError, match="Invalid state"):
            await svc.send_key("D1", first_key, state="invalid_state")


class TestSetVolume:
    @pytest.mark.asyncio
    async def test_invalid_volume_raises(self):
        svc = _make_service()
        with pytest.raises(DomainValidationError, match="Volume must be 0-100"):
            await svc.set_volume("D1", 150)

    @pytest.mark.asyncio
    async def test_negative_volume_raises(self):
        svc = _make_service()
        with pytest.raises(DomainValidationError, match="Volume must be 0-100"):
            await svc.set_volume("D1", -1)
