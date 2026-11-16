"""DLNA application service."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import TypeVar
from urllib.parse import urlsplit

from opencloudtouch.dlna.client import DlnaClient, DlnaTimeoutError
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer, is_audio_item

T = TypeVar("T")


class DlnaService:
    """Discover and browse DLNA media servers."""

    def __init__(
        self,
        discovery: DlnaDiscovery | None = None,
        client: DlnaClient | None = None,
        cache_ttl: float = 60.0,
        missing_ttl: float = 3.0,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = 15.0,
    ):
        self.discovery = discovery or DlnaDiscovery()
        self.client = client or DlnaClient(timeout)
        self._timeout = timeout
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
        # Expired unknown IDs must not accumulate across refreshes.
        for server_id, expires_at in list(self._missing_ids.items()):
            if now >= expires_at:
                del self._missing_ids[server_id]
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

    async def _run(self, operation: Awaitable[T], deadline: float | None) -> T:
        """Run *operation* under the total deadline (callers may pass a shorter one)."""
        limit = self._timeout if deadline is None else min(deadline, self._timeout)
        try:
            async with asyncio.timeout(limit):
                return await operation
        except TimeoutError:
            raise DlnaTimeoutError("DLNA operation exceeded its deadline") from None

    async def browse(
        self,
        server_id: str,
        object_id: str = "0",
        starting_index: int = 0,
        requested_count: int = 50,
        deadline: float | None = None,
    ) -> BrowsePage:
        """Browse one page: containers and audio items only, covers sanitised."""
        page = await self._run(
            self._browse(server_id, object_id, starting_index, requested_count),
            deadline,
        )
        items = [
            self._sanitize(item)
            for item in page.items
            if item.is_container or is_audio_item(item)
        ]
        return BrowsePage(items, page.number_returned, page.total_matches)

    async def get_object(
        self, server_id: str, object_id: str, deadline: float | None = None
    ) -> DlnaItem:
        """Fetch the metadata of one object."""
        item = await self._run(self._get_object(server_id, object_id), deadline)
        return self._sanitize(item)

    async def _browse(
        self, server_id: str, object_id: str, starting_index: int, requested_count: int
    ) -> BrowsePage:
        server = await self._lookup_server(server_id)
        return await self.client.browse(
            server, object_id, starting_index, requested_count
        )

    async def _get_object(self, server_id: str, object_id: str) -> DlnaItem:
        server = await self._lookup_server(server_id)
        return await self.client.get_object(server, object_id)

    @staticmethod
    def _sanitize(item: DlnaItem) -> DlnaItem:
        """Keep ``album_art_url`` only if it is an absolute http(s) URL."""
        if item.album_art_url is None:
            return item
        parts = urlsplit(item.album_art_url)
        if parts.scheme in {"http", "https"} and parts.netloc:
            return item
        return replace(item, album_art_url=None)

    async def _lookup_server(self, server_id: str) -> DlnaServer:
        """Find a cached server, refreshing discovery only when necessary."""
        async with self._discovery_lock:
            missing_until = self._missing_ids.get(server_id, 0.0)
            if self._clock() >= self._cache_expires_at or (
                self._servers
                and not self._last_discovery_empty
                and server_id not in self._servers
                and self._clock() >= missing_until
            ):
                await self._discover_servers()
                # Briefly cache misses after a refresh, including empty scans.
                if (
                    server_id not in self._servers
                    and self._cache_expires_at > self._clock()
                ):
                    self._missing_ids[server_id] = self._clock() + self.missing_ttl
            server = self._servers.get(server_id)

        if server is None:
            raise LookupError(f"DLNA server not found: {server_id}")

        return server
