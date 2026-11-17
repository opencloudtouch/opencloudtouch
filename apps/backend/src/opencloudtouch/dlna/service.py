"""DLNA application service."""

import asyncio
import ipaddress
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from functools import partial
from typing import TypeVar
from urllib.parse import urlsplit

from opencloudtouch.dlna.browse_cache import BrowseCache, CacheKey
from opencloudtouch.dlna.client import (
    DlnaBrowseError,
    DlnaClient,
    DlnaEmptyMetadataError,
    DlnaTimeoutError,
)
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
REVALIDATION_BACKOFF = 30.0  # seconds before a failed key is revalidated again
REFRESH_MIN_INTERVAL = 2.0  # seconds between two forced refreshes of one key
MAX_PATH_DEPTH = 16  # ancestor levels resolved for one object


class DlnaNotPlayableError(Exception):
    """The object has no audio the speaker may fetch (message carries no URLs/titles)."""


@dataclass(frozen=True)
class ResolvedDlnaItem:
    """Current playback data of a DLNA object, taken from the server's own answer."""

    title: str
    resource_url: str
    album_art_url: str | None
    is_container: bool = False


@dataclass(frozen=True)
class ObjectPath:
    """An object with its ancestor folders, top first (root and object excluded)."""

    server_name: str
    item: DlnaItem
    ancestors: list[DlnaItem]


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
        browse_cache: BrowseCache | None = None,
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
        # Without an injected cache the service browses live (cache disabled).
        self._browse_cache = browse_cache or BrowseCache(0, 0, 1, clock=clock)
        self._tasks: set[asyncio.Task[BrowsePage]] = set()
        self._inflight: dict[CacheKey, asyncio.Task[BrowsePage]] = {}
        self._revalidating: dict[str, CacheKey] = {}  # server id -> running key

    def browse_cache_stats(self) -> dict[str, int]:
        """Browse cache counters and limits (no keys, ids or content)."""
        return self._browse_cache.stats()

    async def aclose(self) -> None:
        """Cancel and await every background task (shutdown)."""
        tasks: list[asyncio.Task] = list(self._tasks)
        if self._refresh_task:
            tasks.append(self._refresh_task)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._refresh_task = None

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
        refresh: bool = False,
    ) -> BrowsePage:
        """Browse one page: containers and audio items only, covers sanitised.

        Served from the browse cache first (stale-while-revalidate); ``refresh``
        skips the cache read. The press path never goes through here.
        """
        cache = self._browse_cache
        key = (server_id, object_id, starting_index, requested_count)
        if not cache.enabled:
            return self._filter(await self._run(self._browse(*key), deadline))
        if refresh:
            return await self._refresh(key, deadline)
        hit = cache.get(key)
        if hit is None:
            cache.count("misses")
            return await self._shared(key, deadline, revalidate=False)
        if not hit.stale:
            cache.count("hits_fresh")
            return hit
        cache.count("hits_stale")
        return replace(hit, revalidating=self._revalidate(key))

    def _filter(self, page: BrowsePage) -> BrowsePage:
        items = [
            self._sanitize(item)
            for item in page.items
            if item.is_container or is_audio_item(item)
        ]
        return BrowsePage(items, page.number_returned, page.total_matches)

    async def _refresh(self, key: CacheKey, deadline: float | None) -> BrowsePage:
        cache = self._browse_cache
        if key[0] in self._servers and cache.refreshed_within(
            key, REFRESH_MIN_INTERVAL
        ):
            hit = cache.get(key)
            if hit is not None:
                cache.count("refresh_throttled")
                return replace(hit, revalidating=key in self._inflight)
        cache.count("forced_refreshes")
        page = await self._shared(key, deadline, revalidate=False)
        cache.stamp_refresh(key)
        return page

    async def _shared(
        self, key: CacheKey, deadline: float | None, *, revalidate: bool
    ) -> BrowsePage:
        """Await the one fetch per key; a leaving waiter never cancels it."""
        task = self._inflight.get(key)
        if task is None:
            task = self._spawn(key, revalidate)
        else:
            self._browse_cache.count("coalesced")
        page = await self._run(asyncio.shield(task), deadline)
        return replace(page, items=list(page.items))  # waiters never share a list

    def _revalidate(self, key: CacheKey) -> bool:
        """Start a background revalidation; True while one runs for *key*."""
        if key in self._inflight:
            return True
        if self._browse_cache.in_backoff(key) or key[0] in self._revalidating:
            return False
        self._spawn(key, True)
        return True

    def _spawn(self, key: CacheKey, revalidate: bool) -> asyncio.Task[BrowsePage]:
        task = asyncio.create_task(self._load(key, revalidate))
        self._tasks.add(task)
        self._inflight[key] = task
        if revalidate:
            self._revalidating[key[0]] = key
        task.add_done_callback(partial(self._task_done, key, revalidate))
        return task

    def _task_done(
        self, key: CacheKey, revalidate: bool, task: asyncio.Task[BrowsePage]
    ) -> None:
        self._tasks.discard(task)
        if self._inflight.get(key) is task:
            del self._inflight[key]
        if revalidate and self._revalidating.get(key[0]) == key:
            del self._revalidating[key[0]]
        if not task.cancelled():
            task.exception()  # retrieved: never "exception was never retrieved"

    async def _load(self, key: CacheKey, revalidate: bool) -> BrowsePage:
        cache = self._browse_cache
        token = cache.generation(key[0])
        started = self._clock()
        try:
            page = self._filter(await self._run(self._browse(*key), None))
        except Exception as exc:
            if getattr(exc, "error_code", None) == "701":
                cache.drop(key)
            elif revalidate:
                cache.mark_failed(key, REVALIDATION_BACKOFF)
            if revalidate:
                cache.count("revalidations_failed")
                logger.debug(
                    "DLNA revalidation failed after %.2f s", self._clock() - started
                )
            raise
        cache.put(key, page, token)
        if revalidate:
            cache.count("revalidations_ok")
            logger.debug(
                "DLNA revalidation ok after %.2f s (%d items)",
                self._clock() - started,
                len(page.items),
            )
        return page

    async def get_object(
        self, server_id: str, object_id: str, deadline: float | None = None
    ) -> DlnaItem:
        """Fetch the metadata of one object."""
        item = await self._run(self._get_object(server_id, object_id), deadline)
        return self._sanitize(item)

    async def get_object_path(self, server_id: str, object_id: str) -> ObjectPath:
        """Object plus its ancestors; one deadline covers the whole live walk."""
        return await self._run(self._object_path(server_id, object_id), None)

    async def _object_path(self, server_id: str, object_id: str) -> ObjectPath:
        try:
            return await self._walk_path(server_id, object_id)
        except DlnaEmptyMetadataError:
            # an empty answer means the object is gone (only here, not on the press path)
            raise DlnaBrowseError("No Such Object", error_code="701") from None

    async def _walk_path(self, server_id: str, object_id: str) -> ObjectPath:
        server = await self._lookup_server(server_id)
        if object_id == "0":
            root = DlnaItem("0", "-1", server.name, True)
            return ObjectPath(server.name, root, [])
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
