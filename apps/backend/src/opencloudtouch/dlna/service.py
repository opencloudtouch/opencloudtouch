"""DLNA application service."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import replace
from urllib.parse import urlsplit

from opencloudtouch.dlna.client import DlnaBrowseError, DlnaClient
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.models import (
    BrowsePage,
    DlnaItem,
    DlnaServer,
    ObjectPath,
    is_audio_item,
)

MAX_PATH_DEPTH = 16
ALBUM_SEARCH_MAX_CALLS = 20
ALBUM_SEARCH_MAX_DEPTH = 3
ALBUM_CLASS = "object.container.album.musicAlbum"


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

    async def _resolve(self, server_id: str) -> DlnaServer:
        """Find a server, refreshing discovery only when necessary."""
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

    async def browse_page(
        self,
        server_id: str,
        object_id: str = "0",
        starting_index: int = 0,
        requested_count: int = 50,
    ) -> BrowsePage:
        """Browse live (no browse cache); keep folders and audio only."""
        server = await self._resolve(server_id)
        page = await self.client.browse(
            server, object_id, starting_index, requested_count
        )
        host = urlsplit(server.control_url).hostname
        items = []
        for item in page.items:
            if not (item.is_container or is_audio_item(item)):
                continue
            art = urlsplit(item.album_art_url or "")
            # A cover from another host would make the browser fetch foreign URLs.
            if item.album_art_url and not (
                art.scheme in ("http", "https") and art.hostname == host
            ):
                item = replace(item, album_art_url=None)
            items.append(item)
        return BrowsePage(items, page.number_returned, page.total_matches)

    async def first_child_is_audio(self, server_id: str, container_id: str) -> bool:
        """True if the first child of the container is an audio item."""
        server = await self._resolve(server_id)
        page = await self.client.browse(server, container_id, 0, 1)
        return bool(page.items) and is_audio_item(page.items[0])

    async def get_object_path(self, server_id: str, object_id: str) -> ObjectPath:
        """Object plus its ancestors, read live."""
        server = await self._resolve(server_id)
        if object_id == "0":
            return ObjectPath(server.name, DlnaItem("0", "-1", server.name, True), [])
        item = await self.client.get_object(server, object_id)
        seen = {object_id}
        ancestors: list[DlnaItem] = []
        parent_id = item.parent_id
        while parent_id not in ("0", "-1"):
            if not parent_id or parent_id in seen or len(ancestors) >= MAX_PATH_DEPTH:
                raise DlnaBrowseError("DLNA object path is not resolvable")
            seen.add(parent_id)
            parent = await self.client.get_object(server, parent_id)
            ancestors.append(parent)
            parent_id = parent.parent_id
        ancestors.reverse()
        return ObjectPath(server.name, item, ancestors)

    async def find_album_root(self, server_id: str) -> str | None:
        """First container (breadth-first) directly holding music albums, or None."""
        server = await self._resolve(server_id)
        queue = [("0", 0)]
        calls = 0
        while queue and calls < ALBUM_SEARCH_MAX_CALLS:
            object_id, depth = queue.pop(0)
            calls += 1
            page = await self.client.browse(server, object_id, 0, 200)
            containers = [i for i in page.items if i.is_container]
            if any(i.media_class == ALBUM_CLASS for i in containers):
                return object_id
            if depth < ALBUM_SEARCH_MAX_DEPTH:
                queue.extend((i.id, depth + 1) for i in containers)
        return None
