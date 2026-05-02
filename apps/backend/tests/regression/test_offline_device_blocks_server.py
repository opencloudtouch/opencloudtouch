"""
Regression test: Offline device blocks entire server via sync BoseClient calls.

Date: 2026-04-06
Symptom: Removing one device from the network causes ALL other devices to show
         blurred skeleton tiles instead of presets. Database wipe required.

Root Cause: BoseDeviceClientAdapter calls synchronous bosesoundtouchapi methods
            (GetNowPlayingStatus, GetVolume, etc.) directly in async methods,
            blocking the asyncio event loop for the full connectTimeout (5s).
            During that time, the server cannot serve ANY other request.

Fix: All synchronous BoseClient calls wrapped in asyncio.to_thread().
"""

import asyncio
import inspect
import re
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from opencloudtouch.db import Device, DeviceRepository
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService


@pytest.fixture
async def shared_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        device_repo = DeviceRepository(str(db_path))
        await device_repo.initialize()
        preset_repo = PresetRepository(str(db_path))
        await preset_repo.initialize()
        yield device_repo, preset_repo
        await device_repo.close()
        await preset_repo.close()


def _make_device(device_id: str, ip: str, name: str) -> Device:
    return Device(
        device_id=device_id,
        ip=ip,
        name=name,
        model="SoundTouch 10",
        mac_address=f"AA:BB:CC:DD:EE:{device_id[-2:]}",
        firmware_version="28.0.3",
    )


class TestOfflineDeviceBlocksEventLoop:
    """Regression: synchronous BoseClient calls must not block the event loop."""

    @pytest.mark.asyncio
    async def test_sync_bose_call_does_not_block_event_loop(self, shared_db):
        """A slow device must NOT prevent fast DB reads for other devices.

        Uses the REAL BoseDeviceClientAdapter (with mocked BoseClient) to verify
        that asyncio.to_thread() is correctly applied.
        """
        device_repo, preset_repo = shared_db

        await device_repo.upsert(_make_device("OFFLINE01", "192.168.1.99", "Offline"))
        await device_repo.upsert(_make_device("WORKING01", "192.168.1.10", "Working"))
        for i in range(1, 4):
            await preset_repo.set_preset(
                Preset(
                    device_id="WORKING01",
                    preset_number=i,
                    station_uuid=f"uuid-{i}",
                    station_name=f"Radio {i}",
                    station_url=f"http://stream{i}.example.com/live.mp3",
                )
            )

        BLOCK_SECONDS = 2.0
        preset_service = PresetService(preset_repo, device_repo)

        def slow_get_now_playing():
            """Simulates BoseClient.GetNowPlayingStatus() on an unreachable
            device — blocks the calling thread for connectTimeout seconds."""
            time.sleep(BLOCK_SECONDS)
            raise ConnectionError("Device offline")

        mock_bose_client = MagicMock()
        mock_bose_client.GetNowPlayingStatus = slow_get_now_playing

        preset_timing = []
        np_error = []

        async def poll_offline_now_playing():
            """Call get_now_playing via the REAL adapter with mocked BoseClient."""
            try:
                from opencloudtouch.devices.client_adapter import (
                    BoseDeviceClientAdapter,
                )

                adapter = BoseDeviceClientAdapter.__new__(BoseDeviceClientAdapter)
                adapter.base_url = "http://192.168.1.99:8090"
                adapter.ip = "192.168.1.99"
                adapter.timeout = 5.0
                adapter._client = mock_bose_client

                await adapter.get_now_playing()
            except Exception as e:
                np_error.append(str(e))

        async def read_working_presets():
            start = time.monotonic()
            presets = await preset_service.get_all_presets("WORKING01")
            elapsed = time.monotonic() - start
            preset_timing.append(elapsed)
            return presets

        # Blocking call FIRST — it gets scheduled first in the event loop.
        # Before the fix, this would block the entire event loop for BLOCK_SECONDS,
        # delaying all other coroutines. After the fix (asyncio.to_thread()),
        # it runs in a thread pool and preset reads proceed immediately.
        await asyncio.gather(poll_offline_now_playing(), read_working_presets())

        assert preset_timing[0] < 0.5, (
            f"Preset read took {preset_timing[0]:.2f}s — expected < 0.5s. "
            f"The offline device's synchronous I/O is blocking the event loop. "
            f"BoseClient calls must be wrapped in asyncio.to_thread()."
        )
        assert len(np_error) == 1

    @pytest.mark.asyncio
    async def test_all_bose_methods_use_to_thread(self):
        """Static analysis: every sync BoseClient call must use asyncio.to_thread.

        Reads the source of BoseDeviceClientAdapter and verifies that every
        self._client.Method(...) call is wrapped in asyncio.to_thread().
        Catches regressions where someone adds a new BoseClient call without
        the thread wrapper.
        """
        from opencloudtouch.devices.client_adapter import BoseDeviceClientAdapter

        source = inspect.getsource(BoseDeviceClientAdapter)

        # Find all self._client.MethodName references that are method calls
        # (either direct calls `self._client.Foo(...)` or passed to to_thread)
        # Exclude property accesses like `self._client.Device.DeviceId`
        all_method_refs = set(
            re.findall(r"self\._client\.([A-Z]\w+?)(?:\(|,|\)|\s)", source)
        )

        # Property accesses (no parentheses, used as attribute lookups)
        property_accesses = set(re.findall(r"self\._client\.([A-Z]\w+)\.\w+", source))

        # Methods that are actually called (not just property access)
        called_methods = all_method_refs - property_accesses

        assert called_methods, "Expected at least one self._client.Method() call"

        # Every called method must appear in an asyncio.to_thread() wrapper
        for method in called_methods:
            pattern = rf"asyncio\.to_thread\(self\._client\.{method}"
            assert re.search(pattern, source), (
                f"self._client.{method}() is NOT wrapped in asyncio.to_thread(). "
                f"This will block the event loop when the device is offline."
            )

        # Negative check: no direct calls without to_thread
        # Match self._client.Method( that is NOT preceded by asyncio.to_thread(
        for method in called_methods:
            direct_call = rf"(?<!to_thread\()self\._client\.{method}\("
            matches = re.findall(direct_call, source)
            assert not matches, (
                f"Found direct call self._client.{method}() without asyncio.to_thread(). "
                f"All sync BoseClient calls MUST go through asyncio.to_thread()."
            )

    @pytest.mark.asyncio
    async def test_concurrent_preset_reads_unblocked(self, shared_db):
        """Multiple concurrent preset reads must all complete fast."""
        device_repo, preset_repo = shared_db

        await device_repo.upsert(_make_device("DEAD01", "10.0.0.99", "Dead"))
        for idx in range(3):
            did = f"LIVE{idx:02d}"
            await device_repo.upsert(
                _make_device(did, f"192.168.1.{10 + idx}", f"Speaker {idx}")
            )
            for p in range(1, 4):
                await preset_repo.set_preset(
                    Preset(
                        device_id=did,
                        preset_number=p,
                        station_uuid=f"uuid-{did}-{p}",
                        station_name=f"Radio {p}",
                        station_url=f"http://stream.example.com/{p}.mp3",
                    )
                )

        BLOCK_SECONDS = 2.0
        preset_service = PresetService(preset_repo, device_repo)

        def slow_bose_call():
            time.sleep(BLOCK_SECONDS)
            raise ConnectionError("Device offline")

        mock_bose_client = MagicMock()
        mock_bose_client.GetNowPlayingStatus = slow_bose_call

        timings: dict[str, float] = {}

        async def blocking_call():
            try:
                from opencloudtouch.devices.client_adapter import (
                    BoseDeviceClientAdapter,
                )

                adapter = BoseDeviceClientAdapter.__new__(BoseDeviceClientAdapter)
                adapter.base_url = "http://10.0.0.99:8090"
                adapter.ip = "10.0.0.99"
                adapter.timeout = 5.0
                adapter._client = mock_bose_client
                await adapter.get_now_playing()
            except Exception:
                pass

        async def read_presets(device_id: str):
            start = time.monotonic()
            await preset_service.get_all_presets(device_id)
            timings[device_id] = time.monotonic() - start

        await asyncio.gather(
            blocking_call(),
            read_presets("LIVE00"),
            read_presets("LIVE01"),
            read_presets("LIVE02"),
        )

        for did, elapsed in timings.items():
            assert (
                elapsed < 0.5
            ), f"Preset read for {did} took {elapsed:.2f}s — blocked by offline device."
