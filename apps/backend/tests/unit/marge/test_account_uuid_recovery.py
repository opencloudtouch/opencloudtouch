"""Bounded read-only account UUID recovery tests for issue 511."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.marge.service import MargeService


def _service():
    device_repo = AsyncMock()
    device_repo.get_by_account_uuid.return_value = None
    device_repo.get_by_device_id.return_value = None
    speaker = MagicMock()
    speaker.device_id = "AABBCCDDEEFF"
    speaker.ip = "192.168.1.10"
    device_repo.get_all.return_value = [speaker]
    service = MargeService(AsyncMock(), AsyncMock(), device_repo)
    return service, device_repo, speaker


@pytest.mark.asyncio
async def test_unknown_uuid_recovered_from_known_speaker():
    service, repo, speaker = _service()
    with (
        patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value="7654321",
        ) as reader,
        patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
        ) as writer,
    ):
        assert (
            await service.resolve_device_id_for_account("7654321") == speaker.device_id
        )
        reader.assert_awaited_once()
        writer.assert_not_awaited()
    repo.update_marge_account_uuid.assert_awaited_once_with(
        speaker.device_id, "7654321"
    )


@pytest.mark.asyncio
async def test_repeated_unknown_uuid_does_not_reprobe_within_five_seconds():
    service, repo, _ = _service()
    with patch(
        "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
        new_callable=AsyncMock,
        return_value="1111111",
    ) as reader:
        assert await service.resolve_device_id_for_account("7654321") is None
        assert await service.resolve_device_id_for_account("7654321") is None
        reader.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_device_probe_for_invalid_account_id():
    service, repo, _ = _service()
    with patch(
        "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
        new_callable=AsyncMock,
    ) as reader:
        assert await service.resolve_device_id_for_account("unknown") is None
        reader.assert_not_awaited()


@pytest.mark.asyncio
async def test_three_scans_max_per_minute():
    service, repo, _ = _service()
    times = iter([0, 6, 12, 18])
    with (
        patch("opencloudtouch.marge.service._uuid_refresh_now", side_effect=times),
        patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value="1111111",
        ) as reader,
    ):
        for _ in range(4):
            assert await service.resolve_device_id_for_account("7654321") is None
    assert reader.await_count == 3


@pytest.mark.asyncio
async def test_concurrent_requests_share_uuid_recovery_result():
    """Concurrent requests for the same UUID should share one device scan."""
    import asyncio

    service, repo, speaker = _service()

    # Simulate the database state after successful UUID reconciliation.
    stored_uuids = {}

    async def lookup_uuid(uuid):
        return stored_uuids.get(uuid)

    async def save_uuid(device_id, uuid):
        stored_uuids[uuid] = speaker

    repo.get_by_account_uuid.side_effect = lookup_uuid
    repo.update_marge_account_uuid.side_effect = save_uuid

    scan_started = asyncio.Event()
    allow_scan_to_finish = asyncio.Event()

    async def slow_read(*args, **kwargs):
        scan_started.set()
        await allow_scan_to_finish.wait()
        return "7654321"

    with patch(
        "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
        new_callable=AsyncMock,
        side_effect=slow_read,
    ) as reader:
        first = asyncio.create_task(service.resolve_device_id_for_account("7654321"))
        await asyncio.wait_for(scan_started.wait(), timeout=2)

        second = asyncio.create_task(service.resolve_device_id_for_account("7654321"))

        await asyncio.sleep(0)
        allow_scan_to_finish.set()

        results = await asyncio.gather(first, second)

    assert results == [speaker.device_id, speaker.device_id]
    reader.assert_awaited_once()
    repo.update_marge_account_uuid.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_uuid_recovery_with_real_sqlite():
    """Two simultaneous requests share one scan and persist the UUID in SQLite."""
    import asyncio

    from opencloudtouch.devices.repository import Device, DeviceRepository

    repo = DeviceRepository(":memory:")
    await repo.initialize()

    try:
        speaker = Device(
            device_id="AABBCCDDEEFF",
            ip="192.168.1.10",
            name="Speaker",
            model="SoundTouch 10",
            mac_address="AA:BB:CC:DD:EE:FF",
            firmware_version="27.0.6",
            marge_account_uuid="1234567",
        )
        await repo.upsert(speaker)

        service = MargeService(AsyncMock(), AsyncMock(), repo)
        started = asyncio.Event()
        finish = asyncio.Event()

        async def read_uuid(*args, **kwargs):
            started.set()
            await finish.wait()
            return "7654321"

        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            side_effect=read_uuid,
        ) as reader:
            first = asyncio.create_task(
                service.resolve_device_id_for_account("7654321")
            )

            try:
                await asyncio.wait_for(started.wait(), timeout=2)

                second = asyncio.create_task(
                    service.resolve_device_id_for_account("7654321")
                )
                await asyncio.sleep(0)
            finally:
                finish.set()

            results = await asyncio.gather(first, second)

        assert results == [speaker.device_id, speaker.device_id]
        reader.assert_awaited_once()

        stored = await repo.get_by_account_uuid("7654321")
        assert stored is not None
        assert stored.device_id == speaker.device_id
        assert await repo.get_by_account_uuid("1234567") is None

    finally:
        await repo.close()


@pytest.mark.asyncio
async def test_uuid_recovery_handles_database_collision():
    """A competing UUID assignment must not break the account request."""
    service, repo, speaker = _service()
    repo.update_marge_account_uuid.side_effect = ValueError("UUID collision")
    with patch(
        "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
        new_callable=AsyncMock,
        return_value="7654321",
    ):
        assert await service.resolve_device_id_for_account("7654321") is None
    repo.update_marge_account_uuid.assert_awaited_once_with(
        speaker.device_id, "7654321"
    )
