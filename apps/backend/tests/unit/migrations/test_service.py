"""Tests for the per-speaker migration runner."""

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.devices.repository import Device
from opencloudtouch.devices.websocket.connection import ConnectionState
from opencloudtouch.migrations import service as migration_service
from opencloudtouch.migrations.repository import SpeakerMigrationRepository
from opencloudtouch.migrations.service import SpeakerMigrationService


def _device(device_id: str) -> Device:
    return Device(
        device_id=device_id,
        ip="192.0.2.10",
        name="Speaker",
        model="SoundTouch 10",
        mac_address="000000000000",
        firmware_version="27.0.6",
    )


@pytest.fixture
async def repo(tmp_path):
    repository = SpeakerMigrationRepository(tmp_path / "migrations.db")
    await repository.initialize()
    try:
        yield repository
    finally:
        await repository.close()


def _service(repo, steps, devices=()):
    device_repo = AsyncMock()
    device_repo.get_all.return_value = list(devices)
    device_repo.get_by_device_id.side_effect = lambda device_id: next(
        (d for d in devices if d.device_id == device_id), None
    )
    return SpeakerMigrationService(repo, device_repo, steps=steps)


async def test_runs_steps_in_order_and_stores_version(repo):
    calls = []

    async def step0(device):
        calls.append(0)

    async def step1(device):
        calls.append(1)

    service = _service(repo, {1: step1, 0: step0})
    assert await service.run(_device("device-a")) == 2
    assert calls == [0, 1]
    assert await service.status("device-a") == (2, None)


async def test_failed_step_keeps_version_and_records_reason(repo):
    later = AsyncMock()

    async def failing(device):
        raise RuntimeError("speaker refused")

    service = _service(repo, {0: failing, 1: later})
    assert await service.run(_device("device-a")) == 0
    assert await service.status("device-a") == (0, "RuntimeError: speaker refused")
    later.assert_not_awaited()


async def test_rerun_after_failure_clears_error(repo):
    attempts = []

    async def flaky(device):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("offline")

    service = _service(repo, {0: flaky})
    await service.run(_device("device-a"))
    assert await service.status("device-a") == (0, "OSError: offline")
    assert await service.run(_device("device-a")) == 1
    assert await service.status("device-a") == (1, None)


async def test_steps_logged_with_duration(repo, caplog):
    async def ok(device):
        pass

    async def failing(device):
        raise RuntimeError("boom")

    service = _service(repo, {0: ok, 1: failing})
    with caplog.at_level(logging.INFO, logger="opencloudtouch.migrations.service"):
        await service.run(_device("device-a"))
    text = caplog.text
    assert "[MIGRATION] device-a step 0->1 start" in text
    assert "[MIGRATION] device-a step 0->1 ok" in text
    assert "[MIGRATION] device-a step 1->2 start" in text
    assert "[MIGRATION] device-a step 1->2 failed" in text
    assert "RuntimeError: boom" in text
    assert text.count("ms") >= 2


async def test_run_all_continues_after_one_device_fails(repo):
    async def step(device):
        if device.device_id == "device-a":
            raise RuntimeError("down")

    devices = [_device("device-a"), _device("device-b")]
    service = _service(repo, {0: step}, devices)
    await service.run_all()
    assert await service.status("device-a") == (0, "RuntimeError: down")
    assert await service.status("device-b") == (1, None)


async def test_run_all_survives_unexpected_error(repo):
    devices = [_device("device-a"), _device("device-b")]
    service = _service(repo, {}, devices)
    service.run = AsyncMock(side_effect=[RuntimeError("db"), 0])
    await service.run_all()
    assert service.run.await_count == 2


async def test_one_run_per_device_at_a_time(repo):
    running = 0
    peak = 0

    async def slow(device):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1

    service = _service(repo, {0: slow})
    results = await asyncio.gather(
        service.run(_device("device-a")), service.run(_device("device-a"))
    )
    assert peak == 1
    assert results == [1, 1]


async def test_empty_registry_records_version_zero(repo):
    devices = [_device("device-a")]
    service = _service(repo, {}, devices)
    await service.run_all()
    assert await repo.get("device-a") == (0, None)


def test_production_registry_is_empty():
    # Decision 20: step 0->1 stays unregistered until verified on hardware.
    assert migration_service.STEPS == {}


async def test_reconnect_hook_triggers_run(repo):
    calls = []

    async def step(device):
        calls.append(device.device_id)

    service = _service(repo, {0: step}, [_device("device-a")])
    await service.on_connection_state("device-a", ConnectionState.RECONNECTING)
    await service.on_connection_state("unknown", ConnectionState.CONNECTED)
    assert calls == []
    await service.on_connection_state("device-a", ConnectionState.CONNECTED)
    assert calls == ["device-a"]
    assert await service.status("device-a") == (1, None)
