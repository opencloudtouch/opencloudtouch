"""Base repository class for SQLite persistence.

Provides common database connection, lifecycle management, and schema
migration support for all repositories.
"""

import logging
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base class for all SQLite repositories.

    Provides common patterns for database initialization, connection management,
    schema migrations, and cleanup.
    Subclasses must implement ``_create_schema()`` to define tables.
    """

    def __init__(self, db_path: str | Path):
        """Initialize base repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database connection and create schema.

        Subclasses should override `_create_schema()` to define tables/indexes.
        """
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self._db = await aiosqlite.connect(str(self.db_path))

        # Enable WAL journal mode for concurrent read/write access
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.commit()

        # Global schema_versions table (shared across all repos in the same DB)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS schema_versions (
                version     INTEGER PRIMARY KEY,
                applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """)
        await self._db.commit()

        # Create schema (implemented by subclasses)
        await self._create_schema()

        logger.info(f"Database initialized: {self.db_path}")

    async def _create_schema(self) -> None:
        """Create database schema (tables, indexes).

        Subclasses MUST implement this method to define their schema.
        """
        raise NotImplementedError(
            "Subclasses must implement _create_schema()"
        )  # pragma: no cover

    async def _apply_migration(self, version: int, description: str, sql: str) -> None:
        """Apply a single schema migration idempotently.

        Checks ``schema_versions`` first; skips if already applied.
        On success, records the version so the migration is never repeated.

        Migration numbers are **global** across all repositories sharing a DB
        file.  Use ranges to avoid collisions (e.g. 1–99 presets, 100–199
        devices, 200–299 settings).

        Args:
            version:     Monotonically increasing migration number.
            description: Human-readable description for the audit log.
            sql:         DDL statement to execute (e.g. ``ALTER TABLE …``).
        """
        cursor = await self._conn.execute(
            "SELECT version FROM schema_versions WHERE version = ?",
            (version,),
        )
        if await cursor.fetchone():
            return  # Already applied — idempotent

        try:
            await self._conn.execute(sql)
        except Exception as e:  # noqa: BLE001
            # Treat "duplicate column name" as idempotent: the column was added
            # directly in the base DDL before migration tracking was introduced.
            if "duplicate column name" in str(e).lower():
                logger.info(
                    "Migration v%d: column already exists, marking as applied",
                    version,
                )
            else:
                raise

        await self._conn.execute(
            "INSERT INTO schema_versions (version, description) VALUES (?, ?)",
            (version, description),
        )
        await self._conn.commit()
        logger.info("Applied schema migration v%d: %s", version, description)

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    def _ensure_initialized(self) -> aiosqlite.Connection:
        """Ensure database is initialized and return connection.

        Returns:
            Active database connection

        Raises:
            RuntimeError: If database not initialized
        """
        if not self._db:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._db

    @property
    def _conn(self) -> aiosqlite.Connection:
        """Return active database connection, raising if not initialized.

        Use in _create_schema() and other internal methods that run post-init.
        """
        return self._ensure_initialized()
