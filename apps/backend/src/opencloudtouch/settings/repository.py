"""Settings repository for managing manual device IPs and application settings."""

import logging
from datetime import UTC, datetime

import aiosqlite

from opencloudtouch.core.repository import BaseRepository

logger = logging.getLogger(__name__)


class SettingsRepository(BaseRepository):
    """Repository for managing settings in SQLite database."""

    async def _create_schema(self) -> None:
        """Create settings tables and indexes."""
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS manual_device_ips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        """
        )

        await self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ip_address ON manual_device_ips(ip_address)
        """
        )

        await self._db.commit()

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
            raise ValueError(f"Invalid IP address format: {ip}")

        try:
            for part in parts:
                if not 0 <= int(part) <= 255:
                    raise ValueError(f"Invalid IP address: {ip}")
        except ValueError:
            raise ValueError(f"Invalid IP address: {ip}")

        try:
            await db.execute(
                """
                INSERT INTO manual_device_ips (ip_address, created_at)
                VALUES (?, ?)
            """,
                (ip, datetime.now(UTC).isoformat()),
            )
            await db.commit()
            logger.info(f"Added manual IP: {ip}")
        except aiosqlite.IntegrityError as e:
            raise ValueError(f"IP address already exists: {ip}") from e

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
            logger.warning(f"Manual IP not found for removal: {ip}")
        else:
            logger.info(f"Removed manual IP: {ip}")

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
                "INSERT INTO manual_device_ips (ip_address) VALUES (?)", (ip,)
            )

        await db.commit()
        logger.info(f"Set {len(ips)} manual IPs")

    async def get_manual_ips(self) -> list[str]:
        """
        Get all manual device IP addresses.

        Returns:
            List of IP addresses
        """
        db = self._ensure_initialized()

        cursor = await db.execute(
            """
            SELECT ip_address FROM manual_device_ips ORDER BY created_at ASC
        """
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
