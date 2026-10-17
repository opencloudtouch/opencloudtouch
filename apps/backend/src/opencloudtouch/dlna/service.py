"""DLNA application service."""

import asyncio
import time
from collections.abc import Callable

from opencloudtouch.dlna.client import DlnaClient
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.models import DlnaItem, DlnaServer


class DlnaService:
    """Discover and browse DLNA media servers."""

    def __init__(
        self,
        discovery: DlnaDiscovery | None = None,
        client: DlnaClient | None = None,
        cache_ttl: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.discovery = discovery or DlnaDiscovery()
        self.client = client or DlnaClient()
        self.cache_ttl = cache_ttl
        self._clock = clock
        self._servers: dict[str, DlnaServer] = {}
        self._cache_expires_at = 0.0
        self._discovery_lock = asyncio.Lock()
        self._missing_ids: set[str] = set()

    async def get_servers(self) -> list[DlnaServer]:
        """Explicitly refresh the list of available DLNA media servers."""
        async with self._discovery_lock:
            return await self._discover_servers()

    async def _discover_servers(self) -> list[DlnaServer]:
        """Discover servers and replace the cache; caller holds the lock."""
        servers = await self.discovery.discover()
        self._servers = {server.id: server for server in servers}
        self._cache_expires_at = self._clock() + self.cache_ttl
        self._missing_ids.clear()
        return servers

    async def browse(
        self,
        server_id: str,
        object_id: str = "0",
    ) -> list[DlnaItem]:
        """Browse a cached server, refreshing discovery only when necessary."""
        async with self._discovery_lock:
            if self._clock() >= self._cache_expires_at or (
                server_id not in self._servers and server_id not in self._missing_ids
            ):
                await self._discover_servers()
                if server_id not in self._servers:
                    self._missing_ids.add(server_id)
            server = self._servers.get(server_id)

        if server is None:
            raise LookupError(f"DLNA server not found: {server_id}")

        return await self.client.browse(server, object_id)
