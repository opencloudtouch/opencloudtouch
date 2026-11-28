"""DLNA application service."""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Literal
from urllib.parse import urlsplit

from opencloudtouch.dlna.client import (
    DlnaBrowseError,
    DlnaClient,
    DlnaSearchUnsupportedError,
)
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

SearchKind = Literal["all", "tracks", "folders"]
_SEARCH_FIELDS = ("dc:title", "upnp:artist", "upnp:album")
_KIND_CLASS = {"tracks": "object.item.audioItem", "folders": "object.container"}
# UPnP errors for an optional action the server does not implement.
_NO_ACTION_ERRORS = ("401", "602")

logger = logging.getLogger(__name__)


def build_search_criteria(q: str, kind: str, caps: list[str]) -> str | None:
    """UPnP SearchCriteria using only listed properties; None without dc:title."""

    def listed(prop: str) -> bool:
        return "*" in caps or prop in caps

    if not listed("dc:title"):
        return None
    term = q.replace("\\", "\\\\").replace('"', '\\"')
    fields = " or ".join(f'{p} contains "{term}"' for p in _SEARCH_FIELDS if listed(p))
    criteria = f"({fields})"
    if kind in _KIND_CLASS and listed("upnp:class"):
        criteria += f' and upnp:class derivedfrom "{_KIND_CLASS[kind]}"'
    return criteria


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
        self._refresh_task: asyncio.Task[None] | None = None
        self._search_caps: dict[str, tuple[float, list[str]]] = {}

    async def get_servers(self) -> list[DlnaServer]:
        """Explicitly refresh the list of available DLNA media servers."""
        async with self._discovery_lock:
            return await self._discover_servers()

    def known_servers(self) -> list[DlnaServer]:
        """Servers found by earlier discoveries; no network access."""
        return list(self._servers.values())

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

    async def resolve(self, server_id: str) -> DlnaServer:
        """Find a server, refreshing discovery only when necessary.

        A known server is returned at once, even from an expired cache: SSDP takes
        seconds, so the refresh then runs in the background (stale-while-revalidate).
        """
        known = self._servers.get(server_id)
        if known is not None:
            if self._clock() >= self._cache_expires_at:
                self.refresh_in_background()
            return known
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

    def refresh_in_background(self) -> None:
        """Start one background discovery; at most one is in flight."""
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._background_refresh())

    async def _background_refresh(self) -> None:
        try:
            async with self._discovery_lock:
                # Another caller may have refreshed while this task waited.
                if self._clock() >= self._cache_expires_at:
                    await self._discover_servers()
        except Exception as exc:  # a failed refresh keeps the cached servers
            logger.warning("Background DLNA discovery failed: %s", type(exc).__name__)

    async def browse_page(
        self,
        server_id: str,
        object_id: str = "0",
        starting_index: int = 0,
        requested_count: int = 50,
    ) -> BrowsePage:
        """Browse live (no browse cache); keep folders and audio only."""
        server = await self.resolve(server_id)
        page = await self.client.browse(
            server, object_id, starting_index, requested_count
        )
        return self._playable_page(server, page, "all")

    async def search_page(
        self,
        server_id: str,
        q: str,
        kind: SearchKind = "all",
        container_id: str = "0",
        starting_index: int = 0,
        requested_count: int = 50,
    ) -> BrowsePage:
        """Search the server's own index below a container (live, no cache)."""
        server = await self.resolve(server_id)
        criteria = build_search_criteria(q, kind, await self._search_caps_for(server))
        if criteria is None:
            raise DlnaSearchUnsupportedError("Media server cannot search by title")
        page = await self.client.search(
            server, container_id, criteria, starting_index, requested_count
        )
        return self._playable_page(server, page, kind)

    async def _search_caps_for(self, server: DlnaServer) -> list[str]:
        """Search capabilities, cached per server for the discovery TTL."""
        cached = self._search_caps.get(server.id)
        if cached is not None and self._clock() < cached[0]:
            return cached[1]
        try:
            caps = await self.client.get_search_capabilities(server)
        except DlnaBrowseError as exc:
            if exc.error_code not in _NO_ACTION_ERRORS:
                raise
            caps = []
        self._search_caps[server.id] = (self._clock() + self.cache_ttl, caps)
        return caps

    @staticmethod
    def _playable_page(
        server: DlnaServer, page: BrowsePage, kind: SearchKind
    ) -> BrowsePage:
        """Keep folders and audio (narrowed by kind); drop foreign cover URLs."""
        host = urlsplit(server.control_url).hostname
        items = []
        for item in page.items:
            if not (item.is_container or is_audio_item(item)):
                continue
            # Also applied locally: servers without searchable upnp:class ignore kind.
            if (kind == "tracks" and item.is_container) or (
                kind == "folders" and not item.is_container
            ):
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
        server = await self.resolve(server_id)
        page = await self.client.browse(server, container_id, 0, 1)
        return bool(page.items) and is_audio_item(page.items[0])

    async def get_object_path(self, server_id: str, object_id: str) -> ObjectPath:
        """Object plus its ancestors, read live."""
        server = await self.resolve(server_id)
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
        server = await self.resolve(server_id)
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
