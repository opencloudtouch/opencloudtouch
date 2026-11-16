"""DLNA application service."""

import asyncio
import ipaddress
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import TypeVar
from urllib.parse import urlsplit

from opencloudtouch.dlna.client import DlnaBrowseError, DlnaClient, DlnaTimeoutError
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.models import (
    BrowsePage,
    DlnaItem,
    DlnaServer,
    is_audio_item,
    page_cursor,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)

PRESS_RESOLVE_BUDGET = 3.0  # seconds the speaker may wait for a preset press
CONTAINER_PAGE_SIZE = 50
CONTAINER_MAX_PAGES = 5  # 250 entries


class DlnaNotPlayableError(Exception):
    """The object has no audio the speaker may fetch (message carries no URLs/titles)."""


@dataclass(frozen=True)
class ResolvedDlnaItem:
    """Current playback data of a DLNA object, taken from the server's own answer."""

    title: str
    resource_url: str
    album_art_url: str | None
    is_container: bool = False


def _host_key(url: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | str | None:
    """Comparable host of *url* (lower case, IPv6 zone and port dropped; no DNS)."""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.split("%", 1)[0].lower()
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return host


def _is_same_host_http(url: str | None, control_url: str) -> bool:
    """http(s) URL on the host of the server's control URL (Decision 7)."""
    if not url:
        return False
    try:
        scheme = urlsplit(url).scheme
    except ValueError:  # malformed URL, e.g. broken IPv6 literal
        return False
    if scheme not in {"http", "https"}:
        return False
    key = _host_key(url)
    return key is not None and key == _host_key(control_url)


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
        self._refresh_task: asyncio.Task[None] | None = None

    def get_cached_server(self, server_id: str) -> DlnaServer | None:
        """Discovery-cache lookup only: never scans the network."""
        return self._servers.get(server_id)

    def schedule_refresh(self) -> None:
        """Start one background discovery unless one is already running."""
        if self._refresh_task and not self._refresh_task.done():
            return
        self._refresh_task = asyncio.create_task(self._background_refresh())

    async def _background_refresh(self) -> None:
        try:
            await self.get_servers()
        except Exception:  # noqa: BLE001 - a failed scan must never surface to a caller
            logger.warning("Background DLNA discovery failed")

    async def list_servers(self) -> list[DlnaServer]:
        """Known servers at once, refreshed by a background scan.

        Waits for a scan only while no server is known yet.
        """
        if not self._servers:
            return await self.get_servers()
        self.schedule_refresh()
        return list(self._servers.values())

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

    async def resolve_playable(
        self,
        server_id: str,
        object_id: str,
        *,
        cache_only: bool,
        deadline: float,
    ) -> ResolvedDlnaItem:
        """Current resource URL and cover of a track, or of the first track of a folder.

        ``cache_only`` (press path) looks the server up in the discovery cache only; a
        miss or an unreachable server schedules one background refresh.
        """
        try:
            return await self._run(
                self._resolve(server_id, object_id, cache_only), deadline
            )
        except (LookupError, DlnaBrowseError) as exc:
            if cache_only and getattr(exc, "error_code", None) != "701":
                self.schedule_refresh()
            raise

    async def _resolve(
        self, server_id: str, object_id: str, cache_only: bool
    ) -> ResolvedDlnaItem:
        if cache_only:
            server = self.get_cached_server(server_id)
            if server is None:
                raise LookupError(f"DLNA server not found: {server_id}")
        else:
            server = await self._lookup_server(server_id)

        item = await self.client.get_object(server, object_id)
        playable = item
        if item.is_container:
            playable = await self._first_audio_item(server, object_id)
        elif not is_audio_item(item):
            raise DlnaNotPlayableError("DLNA object is not audio")
        if not _is_same_host_http(playable.resource_url, server.control_url):
            raise DlnaNotPlayableError("DLNA resource is not playable")

        cover = next(
            (
                art
                for art in (item.album_art_url, playable.album_art_url)
                if _is_same_host_http(art, server.control_url)
            ),
            None,
        )
        assert playable.resource_url is not None  # checked by the host rule above
        return ResolvedDlnaItem(
            item.title, playable.resource_url, cover, item.is_container
        )

    async def _first_audio_item(self, server: DlnaServer, object_id: str) -> DlnaItem:
        index = 0
        for _ in range(CONTAINER_MAX_PAGES):
            page = await self.client.browse(
                server, object_id, index, CONTAINER_PAGE_SIZE
            )
            for child in page.items:
                if not child.is_container and is_audio_item(child):
                    return child
            index, has_more = page_cursor(page, index, CONTAINER_PAGE_SIZE)
            if not has_more:
                break
        raise DlnaNotPlayableError("DLNA container has no playable audio")

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
