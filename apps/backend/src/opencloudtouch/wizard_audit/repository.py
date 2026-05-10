"""Repository for wizard audit log entries and config XML snapshots.

Uses migration range v300–v399 (wizard_audit).
"""

import logging
from datetime import UTC, datetime
from typing import Optional

from opencloudtouch.core.repository import BaseRepository

logger = logging.getLogger(__name__)


class WizardAuditRepository(BaseRepository):
    """SQLite repository for wizard audit trail."""

    async def _create_schema(self) -> None:
        """Create wizard audit tables."""
        # Main audit log – one row per event
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS wizard_audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id   TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL,
                category    TEXT    NOT NULL,
                event       TEXT    NOT NULL,
                step        INTEGER,
                detail      TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wizard_audit_device
            ON wizard_audit_log(device_id)
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wizard_audit_ts
            ON wizard_audit_log(device_id, timestamp)
        """)

        # Config XML snapshots – full XML content per file per moment
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS wizard_config_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id   TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL,
                file_path   TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                trigger     TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wizard_snapshots_device
            ON wizard_config_snapshots(device_id)
        """)

        await self._conn.commit()

    # ------------------------------------------------------------------
    # Audit log operations
    # ------------------------------------------------------------------

    async def add_entry(
        self,
        device_id: str,
        category: str,
        event: str,
        step: Optional[int] = None,
        detail: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """Insert a single audit log entry.

        Args:
            device_id: Bose device MAC/ID
            category:  e.g. 'user_action', 'device_info', 'api_call', 'config_change'
            event:     Short event name, e.g. 'button_click', 'dropdown_change'
            step:      Wizard step number (1-7)
            detail:    JSON-encoded extra data (free-form)
            timestamp: ISO-8601 from frontend; defaults to server time

        Returns:
            Inserted row id
        """
        db = self._ensure_initialized()
        ts = timestamp or datetime.now(UTC).isoformat()
        cursor = await db.execute(
            """
            INSERT INTO wizard_audit_log (device_id, timestamp, category, event, step, detail)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (device_id, ts, category, event, step, detail),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def add_batch(self, entries: list[dict]) -> int:
        """Insert multiple entries in one transaction.

        Each dict must have keys: device_id, category, event.
        Optional keys: step, detail, timestamp.

        Returns:
            Number of rows inserted
        """
        db = self._ensure_initialized()
        now = datetime.now(UTC).isoformat()
        rows = [
            (
                e["device_id"],
                e.get("timestamp") or now,
                e["category"],
                e["event"],
                e.get("step"),
                e.get("detail"),
            )
            for e in entries
        ]
        await db.executemany(
            """
            INSERT INTO wizard_audit_log (device_id, timestamp, category, event, step, detail)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await db.commit()
        return len(rows)

    async def get_entries(
        self, device_id: Optional[str] = None, limit: int = 5000
    ) -> list[dict]:
        """Retrieve audit entries, optionally filtered by device.

        Returns:
            List of dicts with id, device_id, timestamp, category, event, step, detail
        """
        db = self._ensure_initialized()
        if device_id:
            cursor = await db.execute(
                """
                SELECT id, device_id, timestamp, category, event, step, detail
                FROM wizard_audit_log
                WHERE device_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (device_id, limit),
            )
        else:
            cursor = await db.execute(
                """
                SELECT id, device_id, timestamp, category, event, step, detail
                FROM wizard_audit_log
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (limit,),
            )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "device_id": r[1],
                "timestamp": r[2],
                "category": r[3],
                "event": r[4],
                "step": r[5],
                "detail": r[6],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Config snapshot operations
    # ------------------------------------------------------------------

    async def add_config_snapshot(
        self,
        device_id: str,
        file_path: str,
        content: str,
        trigger: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """Store a full config XML snapshot.

        Args:
            device_id: Bose device MAC/ID
            file_path: e.g. '/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml'
            content:   Full XML text
            trigger:   What caused the snapshot, e.g. 'before_modify', 'after_modify'
            timestamp: ISO-8601; defaults to server time

        Returns:
            Inserted row id
        """
        db = self._ensure_initialized()
        ts = timestamp or datetime.now(UTC).isoformat()
        cursor = await db.execute(
            """
            INSERT INTO wizard_config_snapshots (device_id, timestamp, file_path, content, trigger)
            VALUES (?, ?, ?, ?, ?)
            """,
            (device_id, ts, file_path, content, trigger),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def get_config_snapshots(
        self, device_id: Optional[str] = None, limit: int = 500
    ) -> list[dict]:
        """Retrieve config snapshots, optionally filtered by device.

        Returns:
            List of dicts with id, device_id, timestamp, file_path, content, trigger
        """
        db = self._ensure_initialized()
        if device_id:
            cursor = await db.execute(
                """
                SELECT id, device_id, timestamp, file_path, content, trigger
                FROM wizard_config_snapshots
                WHERE device_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (device_id, limit),
            )
        else:
            cursor = await db.execute(
                """
                SELECT id, device_id, timestamp, file_path, content, trigger
                FROM wizard_config_snapshots
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (limit,),
            )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "device_id": r[1],
                "timestamp": r[2],
                "file_path": r[3],
                "content": r[4],
                "trigger": r[5],
            }
            for r in rows
        ]
