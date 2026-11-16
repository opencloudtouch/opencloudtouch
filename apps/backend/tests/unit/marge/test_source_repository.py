"""Tests for the media server source table (AC-A4, A7, A9, A17, A18)."""

import sqlite3

import pytest

from opencloudtouch.marge.source_repository import MargeSourceRepository
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository

SERVER_A = "11111111-2222-3333-4444-555555555555"
SERVER_B = "66666666-7777-8888-9999-aaaaaaaaaaaa"


@pytest.fixture
async def repo(tmp_path):
    repository = MargeSourceRepository(tmp_path / "t.db")
    await repository.initialize()
    yield repository
    await repository.close()


async def test_first_id_is_at_least_20000000(repo):
    row = await repo.upsert("DEV1", SERVER_A, "Music")
    assert row.source_id >= 20000000


async def test_same_server_twice_keeps_id_and_one_row(repo):
    first = await repo.upsert("DEV1", SERVER_A, "Music")
    second = await repo.upsert("DEV1", SERVER_A, "Renamed")
    assert second.source_id == first.source_id
    assert second.display_name == "Renamed"
    assert await repo.count_for_device("DEV1") == 1


async def test_delete_then_create_gives_a_new_id(repo):
    first = await repo.upsert("DEV1", SERVER_A, "Music")
    await repo.delete_for_device("DEV1")
    again = await repo.upsert("DEV1", SERVER_A, "Music")
    assert again.source_id > first.source_id


async def test_same_server_on_two_devices_has_two_rows(repo):
    a = await repo.upsert("DEV1", SERVER_A, "Music")
    b = await repo.upsert("DEV2", SERVER_A, "Music")
    assert a.source_id != b.source_id


async def test_delete_only_removes_the_named_row(repo):
    await repo.upsert("DEV1", SERVER_A, "Music")
    await repo.upsert("DEV1", SERVER_B, "Music")
    await repo.upsert("DEV2", SERVER_A, "Music")

    await repo.delete("DEV1", SERVER_A)

    assert [r.server_id for r in await repo.list_active("DEV1")] == [SERVER_B]
    assert len(await repo.list_active("DEV2")) == 1


async def test_delete_all_removes_every_row(repo):
    await repo.upsert("DEV1", SERVER_A, "Music")
    await repo.upsert("DEV2", SERVER_B, "Music")
    await repo.delete_all()
    assert await repo.list_active("DEV1") == []
    assert await repo.list_active("DEV2") == []


async def test_second_start_is_a_noop_and_rows_survive(tmp_path):
    path = tmp_path / "t.db"
    first = MargeSourceRepository(path)
    await first.initialize()
    row = await first.upsert("DEV1", SERVER_A, "Music")
    await first.close()

    second = MargeSourceRepository(path)
    await second.initialize()
    assert (await second.get_by_id(row.source_id)).server_id == SERVER_A
    assert (await second.upsert("DEV1", SERVER_B, "x")).source_id > row.source_id
    await second.close()


async def test_presets_migration_v2_on_a_previous_schema(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE presets (id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL, preset_number INTEGER NOT NULL,
            station_uuid TEXT NOT NULL, station_name TEXT NOT NULL,
            station_url TEXT NOT NULL, station_homepage TEXT, station_favicon TEXT,
            created_at TIMESTAMP NOT NULL, updated_at TIMESTAMP NOT NULL,
            source TEXT, UNIQUE(device_id, preset_number))""")
        db.execute(
            "INSERT INTO presets (device_id, preset_number, station_uuid, station_name,"
            " station_url, created_at, updated_at, source) VALUES"
            " ('D', 1, 'u', 'n', 'http://x', '2024-01-01T00:00:00', '2024-01-01T00:00:00', 'TUNEIN')"
        )
    presets = PresetRepository(path)
    await presets.initialize()
    old = await presets.get_preset("D", 1)
    assert old is not None and old.native_type is None
    await presets.close()
    again = PresetRepository(path)
    await again.initialize()  # second start: no-op
    await again.close()


async def test_native_type_is_reset_by_a_radio_preset_and_needs_dlna(tmp_path):
    presets = PresetRepository(tmp_path / "p.db")
    await presets.initialize()

    def make(source, native_type):
        return Preset(
            "D", 2, "u", "n", "dlna://s/o", source=source, native_type=native_type
        )

    await presets.set_preset(make("DLNA", "dir"))
    assert (await presets.get_preset("D", 2)).native_type == "dir"
    await presets.set_preset(make("LOCAL_INTERNET_RADIO", None))
    assert (await presets.get_preset("D", 2)).native_type is None
    await presets.set_preset(make("TUNEIN", "dir"))  # ignored: not DLNA
    assert (await presets.get_preset("D", 2)).native_type is None
    await presets.close()
