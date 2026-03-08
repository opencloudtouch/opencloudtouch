"""Tests for preset repository."""

import tempfile
from pathlib import Path

import pytest

from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository


@pytest.fixture
async def preset_repo():
    """Create a temporary preset repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_presets.db"
        repo = PresetRepository(str(db_path))
        await repo.initialize()
        yield repo
        await repo.close()


@pytest.fixture
def sample_preset_data():
    """Sample preset data for testing."""
    return {
        "device_id": "device123",
        "preset_number": 1,
        "station_uuid": "station-uuid-abc",
        "station_name": "Test Radio",
        "station_url": "http://test.radio/stream.mp3",
        "station_homepage": "https://test.radio",
        "station_favicon": "https://test.radio/favicon.ico",
    }


class TestPresetRepository:
    """Tests for PresetRepository."""

    @pytest.mark.asyncio
    async def test_initialize_creates_table(self, preset_repo):
        """Test that initialize creates the presets table."""
        # Table should exist after initialization
        cursor = await preset_repo._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='presets'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "presets"

    @pytest.mark.asyncio
    async def test_set_preset_insert(self, preset_repo, sample_preset_data):
        """Test setting a new preset."""
        preset = Preset(**sample_preset_data)

        result = await preset_repo.set_preset(preset)

        assert result.id is not None
        assert result.device_id == "device123"
        assert result.preset_number == 1
        assert result.station_uuid == "station-uuid-abc"
        assert result.station_name == "Test Radio"

    @pytest.mark.asyncio
    async def test_set_preset_update(self, preset_repo, sample_preset_data):
        """Test updating an existing preset."""
        # Insert initial preset
        preset1 = Preset(**sample_preset_data)
        await preset_repo.set_preset(preset1)

        # Update same device/preset_number with different station
        preset2 = Preset(
            device_id="device123",
            preset_number=1,
            station_uuid="new-station-uuid",
            station_name="New Radio",
            station_url="http://new.radio/stream.mp3",
        )

        result = await preset_repo.set_preset(preset2)

        assert result.station_uuid == "new-station-uuid"
        assert result.station_name == "New Radio"

        # Verify only one preset exists
        all_presets = await preset_repo.get_all_presets("device123")
        assert len(all_presets) == 1
        assert all_presets[0].station_name == "New Radio"

    @pytest.mark.asyncio
    async def test_get_preset_existing(self, preset_repo, sample_preset_data):
        """Test getting an existing preset."""
        preset = Preset(**sample_preset_data)
        await preset_repo.set_preset(preset)

        result = await preset_repo.get_preset("device123", 1)

        assert result is not None
        assert result.device_id == "device123"
        assert result.preset_number == 1
        assert result.station_name == "Test Radio"

    @pytest.mark.asyncio
    async def test_get_preset_nonexistent(self, preset_repo):
        """Test getting a nonexistent preset returns None."""
        result = await preset_repo.get_preset("nonexistent", 1)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_presets_empty(self, preset_repo):
        """Test getting all presets for device with none set."""
        result = await preset_repo.get_all_presets("device123")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_presets_multiple(self, preset_repo):
        """Test getting all presets for a device."""
        # Set presets 1, 3, 5 for device123
        for preset_num in [1, 3, 5]:
            preset = Preset(
                device_id="device123",
                preset_number=preset_num,
                station_uuid=f"uuid-{preset_num}",
                station_name=f"Station {preset_num}",
                station_url=f"http://station{preset_num}.com/stream",
            )
            await preset_repo.set_preset(preset)

        # Set preset 2 for device456
        other_preset = Preset(
            device_id="device456",
            preset_number=2,
            station_uuid="uuid-other",
            station_name="Other Station",
            station_url="http://other.com/stream",
        )
        await preset_repo.set_preset(other_preset)

        result = await preset_repo.get_all_presets("device123")

        assert len(result) == 3
        preset_numbers = [p.preset_number for p in result]
        assert set(preset_numbers) == {1, 3, 5}
        # Verify they're sorted by preset_number
        assert preset_numbers == [1, 3, 5]

    @pytest.mark.asyncio
    async def test_clear_preset_existing(self, preset_repo, sample_preset_data):
        """Test clearing an existing preset."""
        preset = Preset(**sample_preset_data)
        await preset_repo.set_preset(preset)

        deleted_count = await preset_repo.clear_preset("device123", 1)

        assert deleted_count == 1

        # Verify preset is gone
        result = await preset_repo.get_preset("device123", 1)
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_preset_nonexistent(self, preset_repo):
        """Test clearing a nonexistent preset returns 0."""
        deleted_count = await preset_repo.clear_preset("nonexistent", 1)

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_clear_all_presets(self, preset_repo):
        """Test clearing all presets for a device."""
        # Set multiple presets for device123
        for preset_num in [1, 2, 3]:
            preset = Preset(
                device_id="device123",
                preset_number=preset_num,
                station_uuid=f"uuid-{preset_num}",
                station_name=f"Station {preset_num}",
                station_url=f"http://station{preset_num}.com/stream",
            )
            await preset_repo.set_preset(preset)

        # Set preset for device456 (should not be deleted)
        other_preset = Preset(
            device_id="device456",
            preset_number=1,
            station_uuid="uuid-other",
            station_name="Other",
            station_url="http://other.com/stream",
        )
        await preset_repo.set_preset(other_preset)

        deleted_count = await preset_repo.clear_all_presets("device123")

        assert deleted_count == 3

        # Verify device123 presets are gone
        result = await preset_repo.get_all_presets("device123")
        assert result == []

        # Verify device456 preset still exists
        result = await preset_repo.get_all_presets("device456")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_database_not_initialized_error(self):
        """Test that operations fail if database is not initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = PresetRepository(str(db_path))
            # Don't call initialize()

            preset = Preset(
                device_id="device",
                preset_number=1,
                station_uuid="uuid",
                station_name="Station",
                station_url="http://example.com",
            )

            with pytest.raises(RuntimeError, match="Database not initialized"):
                await repo.set_preset(preset)

    @pytest.mark.asyncio
    async def test_unique_constraint_device_preset_number(self, preset_repo):
        """Test that (device_id, preset_number) is unique."""
        preset1 = Preset(
            device_id="device123",
            preset_number=1,
            station_uuid="uuid1",
            station_name="Station 1",
            station_url="http://station1.com",
        )
        preset2 = Preset(
            device_id="device123",
            preset_number=1,
            station_uuid="uuid2",
            station_name="Station 2",
            station_url="http://station2.com",
        )

        # First insert should succeed
        await preset_repo.set_preset(preset1)

        # Second insert with same device_id+preset_number should update
        await preset_repo.set_preset(preset2)

        # Should update, not create duplicate
        all_presets = await preset_repo.get_all_presets("device123")
        assert len(all_presets) == 1
        assert all_presets[0].station_uuid == "uuid2"


# ---------------------------------------------------------------------------
# BUG-34: Missing DB migration for 'source' column
# ---------------------------------------------------------------------------


class TestMigration:
    """
    BUG-34 Regression: Adding 'source' column to the Preset model was done
    without a migration script for existing databases.

    Symptom: existing installations got:
      sqlite3.OperationalError: table presets has no column named source

    Fix: _create_schema() runs ALTER TABLE IF NOT EXISTS analog (SELECT to detect).
    """

    @pytest.mark.asyncio
    async def test_initialize_creates_source_column(self, preset_repo):
        """New database must have source column from the start."""
        # Verify source column exists by trying to use it
        preset = Preset(
            device_id="device_migration",
            preset_number=1,
            station_uuid="uuid-migration",
            station_name="Migration Test",
            station_url="http://migration.test/stream",
            source="INTERNET_RADIO",
        )
        # Should not raise OperationalError
        await preset_repo.set_preset(preset)

        result = await preset_repo.get_preset("device_migration", 1)
        assert result is not None
        assert (
            result.source == "INTERNET_RADIO"
        ), "BUG-34: source field should be stored and retrieved correctly."

    @pytest.mark.asyncio
    async def test_adds_source_column_to_existing_db(self):
        """
        BUG-34: Existing databases (without source column) must be migrated.

        Simulates the real-world scenario: old DB without source column,
        new code that needs it.
        """
        import tempfile
        from pathlib import Path

        import aiosqlite

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "legacy_presets.db"

            # 1. Create old-style DB WITHOUT source column
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("""
                    CREATE TABLE presets (
                        device_id TEXT NOT NULL,
                        preset_number INTEGER NOT NULL,
                        station_uuid TEXT,
                        station_name TEXT NOT NULL,
                        station_url TEXT NOT NULL,
                        station_homepage TEXT,
                        station_favicon TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (device_id, preset_number)
                    )
                """)
                # Insert a row without source column
                await db.execute(
                    "INSERT INTO presets (device_id, preset_number, station_name, station_url) "
                    "VALUES ('device1', 1, 'Old Station', 'http://old.radio/stream')"
                )
                await db.commit()

            # 2. Initialize PresetRepository on the legacy DB (should auto-migrate)
            repo = PresetRepository(str(db_path))
            await repo.initialize()  # Must NOT raise OperationalError

            # 3. Verify source column now exists by doing a raw SQL write/read
            async with aiosqlite.connect(str(db_path)) as db:
                # Get columns of the migrated table
                cursor = await db.execute("PRAGMA table_info(presets)")
                rows = await cursor.fetchall()
                col_names = [row[1] for row in rows]
                assert (
                    "source" in col_names
                ), f"BUG-34: After migration, 'source' column must exist. Columns: {col_names}"

                # Write to source column via raw SQL (avoids the new schema's id column issue)
                await db.execute(
                    "UPDATE presets SET source = 'TUNEIN' "
                    "WHERE device_id = 'device1' AND preset_number = 1"
                )
                await db.commit()

                # Verify the update
                cursor = await db.execute(
                    "SELECT source FROM presets WHERE device_id = 'device1' AND preset_number = 1"
                )
                row = await cursor.fetchone()
                assert row is not None, "Old row must still be present after migration"
                assert (
                    row[0] == "TUNEIN"
                ), f"BUG-34: source column must be writable after migration. Got: {row[0]}"

            await repo.close()

    @pytest.mark.asyncio
    async def test_source_field_can_be_none(self, preset_repo):
        """source field is nullable (TEXT without NOT NULL)."""
        preset = Preset(
            device_id="device_null_source",
            preset_number=1,
            station_uuid="uuid-null",
            station_name="Station Without Source",
            station_url="http://nosource.radio/stream",
            source=None,
        )
        await preset_repo.set_preset(preset)

        result = await preset_repo.get_preset("device_null_source", 1)
        assert result is not None
        assert result.source is None, "source=None should be stored as NULL"


# ---------------------------------------------------------------------------
# REFACT-007: Schema-version table (idempotency + audit trail)
# ---------------------------------------------------------------------------


class TestSchemaVersions:
    """REFACT-007: Verify that the schema-versions tracking table is created
    and that migrations are recorded and not re-applied."""

    @pytest.mark.asyncio
    async def test_schema_versions_table_is_created(self, preset_repo):
        """schema_versions table must exist after initialization."""
        cursor = await preset_repo._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='schema_versions'"
        )
        row = await cursor.fetchone()
        assert row is not None, "schema_versions table must be created on init"

    @pytest.mark.asyncio
    async def test_migration_v1_recorded_in_schema_versions(self, preset_repo):
        """Migration v1 (source column) must be recorded in schema_versions."""
        cursor = await preset_repo._db.execute(
            "SELECT version, description FROM schema_versions WHERE version = 1"
        )
        row = await cursor.fetchone()
        assert row is not None, "Migration v1 must be recorded in schema_versions"
        assert row[0] == 1
        assert "source" in row[1].lower()

    @pytest.mark.asyncio
    async def test_migration_is_idempotent(self):
        """Calling _create_schema twice must not raise and must not duplicate rows."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "idempotent.db"
            repo = PresetRepository(str(db_path))
            await repo.initialize()  # first run

            # Second initialize must be safe (no duplicate-column / unique errors)
            await repo._create_schema()  # type: ignore[attr-defined]

            cursor = await repo._db.execute(
                "SELECT COUNT(*) FROM schema_versions WHERE version = 1"
            )
            row = await cursor.fetchone()
            assert row[0] == 1, (
                "Migration v1 must appear exactly once in schema_versions "
                "even after _create_schema is called twice"
            )
            await repo.close()

    @pytest.mark.asyncio
    async def test_migration_robust_against_duplicate_column(self):
        """Regression test: DB already has source column but NO schema_versions.

        This is the exact scenario that caused startup failure on myserver:
        An older version of the code included 'source' directly in the base
        CREATE TABLE DDL.  When the new code with migration tracking runs,
        schema_versions is empty → migration tries ALTER TABLE ADD COLUMN source
        → sqlite3.OperationalError: duplicate column name: source.

        The fix: _apply_migration must catch 'duplicate column name' and treat
        it as an already-applied migration (idempotent).

        Bug: Application startup failed on myserver after new image deployment.
        Fixed: 2026-03-05 — catch duplicate column name in _apply_migration.
        """
        import tempfile
        from pathlib import Path

        import aiosqlite

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "prod_regression.db"

            # Simulate old-style DB: presets WITH source column, NO schema_versions
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("""
                    CREATE TABLE presets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id TEXT NOT NULL,
                        preset_number INTEGER NOT NULL,
                        station_uuid TEXT NOT NULL,
                        station_name TEXT NOT NULL,
                        station_url TEXT NOT NULL,
                        station_homepage TEXT,
                        station_favicon TEXT,
                        source TEXT,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP,
                        UNIQUE(device_id, preset_number)
                    )
                    """)
                await db.commit()

            # Must NOT raise — this is the myserver crash scenario
            repo = PresetRepository(str(db_path))
            await repo.initialize()

            # schema_versions should now contain migration v1
            async with aiosqlite.connect(str(db_path)) as db:
                cursor = await db.execute(
                    "SELECT version FROM schema_versions WHERE version = 1"
                )
                row = await cursor.fetchone()
                assert (
                    row is not None
                ), "Migration v1 must be recorded even when column already existed"

            await repo.close()
        """Legacy DB (without schema_versions or source column) must be migrated
        and the migration must be recorded in schema_versions with a timestamp."""
        import tempfile
        from pathlib import Path

        import aiosqlite

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "legacy.db"

            # Old-style DB — no source column, no schema_versions table
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("""
                    CREATE TABLE presets (
                        device_id TEXT NOT NULL,
                        preset_number INTEGER NOT NULL,
                        station_name TEXT NOT NULL,
                        station_url TEXT NOT NULL,
                        PRIMARY KEY (device_id, preset_number)
                    )
                    """)
                await db.commit()

            repo = PresetRepository(str(db_path))
            await repo.initialize()

            # source column must now exist
            async with aiosqlite.connect(str(db_path)) as db:
                cursor = await db.execute("PRAGMA table_info(presets)")
                rows = await cursor.fetchall()
                col_names = [r[1] for r in rows]
                assert (
                    "source" in col_names
                ), "REFACT-007: source column must exist after migrating legacy DB"

                # Migration must be recorded
                cursor = await db.execute(
                    "SELECT version, applied_at FROM schema_versions WHERE version = 1"
                )
                row = await cursor.fetchone()
                assert (
                    row is not None
                ), "REFACT-007: Migration v1 must be recorded in schema_versions"
                assert row[1] is not None, "applied_at timestamp must be set"

            await repo.close()
