"""Persistence tests for per-speaker migration versions."""

import pytest

from opencloudtouch.migrations.repository import SpeakerMigrationRepository


@pytest.fixture
async def repo(tmp_path):
    repository = SpeakerMigrationRepository(tmp_path / "migrations.db")
    await repository.initialize()
    try:
        yield repository
    finally:
        await repository.close()


async def test_no_row_is_version_zero(repo):
    assert await repo.get("device-a") == (0, None)


async def test_error_then_version_clears_error(repo):
    await repo.set_error("device-a", "RuntimeError: boom")
    assert await repo.get("device-a") == (0, "RuntimeError: boom")
    await repo.set_version("device-a", 1)
    assert await repo.get("device-a") == (1, None)
    await repo.set_error("device-a", "ValueError: again")
    assert await repo.get("device-a") == (1, "ValueError: again")
