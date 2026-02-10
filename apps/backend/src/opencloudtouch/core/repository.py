"""Base repository class for SQLite persistence.

Provides common database connection and lifecycle management for all repositories.
"""

import logging
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base class for all SQLite repositories.

    Provides common patterns for database initialization, connection management,
    and cleanup. Subclasses must implement `_create_schema()` to define tables.
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

        # Create schema (implemented by subclasses)
        await self._create_schema()

        logger.info(f"Database initialized: {self.db_path}")

    async def _create_schema(self) -> None:
        """Create database schema (tables, indexes).

        Subclasses MUST implement this method to define their schema.
        """
        raise NotImplementedError("Subclasses must implement _create_schema()")

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
