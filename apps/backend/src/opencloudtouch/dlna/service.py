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
        missing_ttl: float = 3.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.discovery = discovery or DlnaDiscovery()
        self.client = client or DlnaClient()
        self.cache_ttl = cache_ttl
        self.missing_ttl = missing_ttl
        self._clock = clock
        self._servers: dict[str, DlnaServer] = {}
        self._last_seen: dict[str, float] = {}
        self._stale_ttl = max(3 * cache_ttl, cache_ttl + missing_ttl)
        self._cache_expires_at = 0.0
        self._last_discovery_empty = False
        self._discovery_lock = asyncio.Lock()
        self._missing_ids: dict[str, float] = {}

    async def get_servers(self) -> list[DlnaServer]:
        """Explicitly refresh the list of available DLNA media servers."""
        async with self._discovery_lock:
            return await self._discover_servers()

    async def _discover_servers(self) -> list[DlnaServer]:
        """Merge SSDP results without evicting servers missed by UDP discovery."""
        servers = await self.discovery.discover()
        now = self._clock()
        self._last_discovery_empty = not servers
        for server in servers:
            self._servers[server.id] = server
            self._last_seen[server.id] = now
            self._missing_ids.pop(server.id, None)

        # One missed UDP response must not evict a previously found server.
        # Yet old entries must eventually disappear, even if scans stay empty.
        for server_id, last_seen in list(self._last_seen.items()):
            if now - last_seen >= self._stale_ttl:
                self._servers.pop(server_id, None)
                del self._last_seen[server_id]

        # Do not retry every incoming request after a failed/empty scan.
        self._cache_expires_at = now + (self.cache_ttl if servers else self.missing_ttl)
        return list(self._servers.values())

    async def browse(
        self,
        server_id: str,
        object_id: str = "0",
    ) -> list[DlnaItem]:
        """Browse a cached server, refreshing discovery only when necessary."""
        async with self._discovery_lock:
            missing_until = self._missing_ids.get(server_id, 0.0)
            if self._clock() >= self._cache_expires_at or (
                self._servers
                and not self._last_discovery_empty
                and server_id not in self._servers
                and self._clock() >= missing_until
            ):
                await self._discover_servers()
                # Only negative-cache a miss after a nonempty discovery.
                if (
                    server_id not in self._servers
                    and self._cache_expires_at > self._clock()
                ):
                    self._missing_ids[server_id] = self._clock() + self.missing_ttl
            server = self._servers.get(server_id)

        if server is None:
            raise LookupError(f"DLNA server not found: {server_id}")

        return await self.client.browse(server, object_id)
