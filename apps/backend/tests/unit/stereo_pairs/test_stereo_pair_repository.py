"""Unit tests for StereoPairRepository."""

import pytest

from opencloudtouch.stereo_pairs.repository import (
    DeviceAlreadyPairedError,
    StereoPairRepository,
)


@pytest.mark.asyncio
class TestStereoPairRepository:
    @pytest.fixture
    async def repo(self, tmp_path):
        repository = StereoPairRepository(str(tmp_path / "pairs.db"))
        await repository.initialize()
        yield repository
        await repository.close()

    async def test_create_and_get_by_device(self, repo):
        pair = await repo.create_pair("Office", "LEFT_1", "LEFT_1", "RIGHT_1")

        assert pair.id is not None
        assert pair.master_device_id == "LEFT_1"
        for device_id in ("LEFT_1", "RIGHT_1"):
            found = await repo.get_by_device(device_id)
            assert found is not None
            assert found.id == pair.id
            assert found.name == "Office"

    async def test_get_by_device_unknown_returns_none(self, repo):
        assert await repo.get_by_device("NOPE") is None

    async def test_device_in_active_pair_is_rejected(self, repo):
        await repo.create_pair("A", "L1", "L1", "R1")

        with pytest.raises(DeviceAlreadyPairedError):
            await repo.create_pair("B", "L2", "L2", "R1")
        with pytest.raises(DeviceAlreadyPairedError):
            await repo.create_pair("C", "L1", "L1", "R3")

    async def test_dissolved_pair_frees_devices(self, repo):
        pair = await repo.create_pair("A", "L1", "L1", "R1")
        await repo.dissolve(pair.id)

        assert await repo.get_by_device("L1") is None
        again = await repo.create_pair("B", "L1", "L1", "R1")
        assert again.id != pair.id

    async def test_dissolve_is_idempotent(self, repo):
        pair = await repo.create_pair("A", "L1", "L1", "R1")
        await repo.dissolve(pair.id)
        await repo.dissolve(pair.id)
        await repo.dissolve(99999)

    async def test_list_active_and_rename(self, repo):
        first = await repo.create_pair("A", "L1", "L1", "R1")
        second = await repo.create_pair("B", "L2", "L2", "R2")
        await repo.dissolve(first.id)
        await repo.rename(second.id, "Renamed")

        pairs = await repo.list_active()
        assert [p.id for p in pairs] == [second.id]
        assert pairs[0].name == "Renamed"

    async def test_status_source_defaults_and_set_status(self, repo):
        pair = await repo.create_pair("A", "L1", "L1", "R1")
        assert (pair.status, pair.source) == ("active", "oct")

        pending = await repo.create_pair(
            "B", "L2", "L2", "R2", status="pending", source="device"
        )
        assert (pending.status, pending.source) == ("pending", "device")

        await repo.set_status(pending.id, "active")
        reloaded = await repo.get(pending.id)
        assert (reloaded.status, reloaded.source) == ("active", "device")

    async def test_delete_removes_row_and_frees_devices(self, repo):
        pair = await repo.create_pair("A", "L1", "L1", "R1", status="pending")
        await repo.delete(pair.id)

        assert await repo.get(pair.id) is None
        assert await repo.get_by_device("L1") is None
