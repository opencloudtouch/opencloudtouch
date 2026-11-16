"""Deleting a device removes its media server registrations (AC-A17)."""

from unittest.mock import AsyncMock

from opencloudtouch.devices.service import DeviceService


def _service(sources):
    return DeviceService(
        repository=AsyncMock(),
        sync_service=AsyncMock(),
        discovery_adapter=AsyncMock(),
        media_server_sources=sources,
    )


async def test_delete_by_device_id_removes_rows():
    sources = AsyncMock()
    service = _service(sources)
    await service.delete_by_device_id("DEV1")
    sources.delete_for_device.assert_awaited_once_with("DEV1")


async def test_delete_all_removes_all_rows():
    sources = AsyncMock()
    service = _service(sources)
    await service.delete_all_devices(allow_dangerous_operations=True)
    sources.delete_all.assert_awaited_once()


async def test_without_a_row_store_deletion_still_works():
    service = _service(None)
    await service.delete_by_device_id("DEV1")
    await service.delete_all_devices(allow_dangerous_operations=True)
