"""Regression: concurrent writers on one shared connection must not fail to commit."""

import asyncio

import pytest

from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository


def _preset(n: int, name: str) -> Preset:
    return Preset(
        device_id="DEV1",
        preset_number=n,
        station_uuid=f"u{n}",
        station_name=name,
        station_url="http://x/y",
        source="DLNA",
    )


@pytest.mark.asyncio
async def test_concurrent_set_preset_does_not_leave_statements_in_progress(tmp_path):
    repo = PresetRepository(tmp_path / "p.db")
    await repo.initialize()
    db = repo._conn
    real_execute, real_fetchall = db.execute, db.execute_fetchall

    async def slow_execute(*args, **kwargs):
        cursor = await real_execute(*args, **kwargs)
        await asyncio.sleep(0.01)  # let the other writers run while A is in progress
        return cursor

    async def slow_fetchall(*args, **kwargs):
        rows = await real_fetchall(*args, **kwargs)
        await asyncio.sleep(0.01)
        return rows

    db.execute = slow_execute  # type: ignore[method-assign]
    db.execute_fetchall = slow_fetchall  # type: ignore[method-assign]
    try:
        for _ in range(20):
            results = await asyncio.gather(
                *(repo.set_preset(_preset(n, f"n{n}")) for n in range(1, 7)),
                *(repo.set_preset(_preset(n, f"m{n}")) for n in range(1, 7)),
            )
            assert all(r.id for r in results)
    finally:
        await repo.close()
