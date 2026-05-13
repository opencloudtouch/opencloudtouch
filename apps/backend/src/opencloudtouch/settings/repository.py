"""Settings repository for managing manual device IPs and application settings."""

import logging
from datetime import UTC, datetime

import aiosqlite

from opencloudtouch.core.exceptions import DomainValidationError
from opencloudtouch.core.repository import BaseRepository

logger = logging.getLogger(__name__)


class SettingsRepository(BaseRepository):
    """Repository for managing settings in SQLite database."""

    async def _create_schema(self) -> None:
        """Create settings tables and indexes."""
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS manual_device_ips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ip_address ON manual_device_ips(ip_address)
        """)

        await self._conn.commit()

    async def add_manual_ip(self, ip: str) -> None:
        """
        Add a manual device IP address.

        Args:
            ip: IP address to add

        Raises:
            ValueError: If IP address is invalid or already exists
        """
        db = self._ensure_initialized()

        # Basic IP validation
        parts = ip.split(".")
        if len(parts) != 4:
            raise DomainValidationError(f"Invalid IP address format: {ip}", field="ip")

        try:
            for part in parts:
                if not 0 <= int(part) <= 255:
                    raise DomainValidationError(f"Invalid IP address: {ip}", field="ip")
        except (DomainValidationError, ValueError):
            raise DomainValidationError(f"Invalid IP address: {ip}", field="ip")

        try:
            await db.execute(
                """
                INSERT INTO manual_device_ips (ip_address, created_at)
                VALUES (?, ?)
            """,
                (ip, datetime.now(UTC).isoformat()),
            )
            await db.commit()
            logger.info("Added manual IP: %s", ip)
        except aiosqlite.IntegrityError as e:
            raise DomainValidationError(
                f"IP address already exists: {ip}", field="ip"
            ) from e

    async def remove_manual_ip(self, ip: str) -> None:
        """
        Remove a manual device IP address.

        Args:
            ip: IP address to remove
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            DELETE FROM manual_device_ips WHERE ip_address = ?
        """,
            (ip,),
        )
        await db.commit()

        if cursor.rowcount == 0:
            logger.warning("Manual IP not found for removal: %s", ip)  # NOSONAR
        else:
            logger.info("Removed manual IP: %s", ip)  # NOSONAR

    async def set_manual_ips(self, ips: list[str]) -> None:
        """
        Replace all manual IPs with provided list.

        Args:
            ips: List of IP addresses to set
        """
        db = self._ensure_initialized()

        # Clear all existing IPs
        await db.execute("DELETE FROM manual_device_ips")

        # Add new IPs
        for ip in ips:
            await db.execute(
                "INSERT INTO manual_device_ips (ip_address, created_at) VALUES (?, ?)",
                (ip, datetime.now(UTC).isoformat()),
            )

        await db.commit()
        logger.info("Set %d manual IPs", len(ips))

    async def get_manual_ips(self) -> list[str]:
        """
        Get all manual device IP addresses.

        Returns:
            List of IP addresses
        """
        db = self._ensure_initialized()

        cursor = await db.execute("""
            SELECT ip_address FROM manual_device_ips ORDER BY created_at ASC
        """)
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
