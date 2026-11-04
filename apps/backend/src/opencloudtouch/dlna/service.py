"""DLNA application service."""

import asyncio
import logging
import time
from collections.abc import Callable

from opencloudtouch.dlna.client import DlnaClient
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.events import DlnaEventSubscriptions
from opencloudtouch.dlna.playback import DlnaPlaybackService
from opencloudtouch.dlna.models import DlnaItem, DlnaServer

logger = logging.getLogger(__name__)


class DlnaService:
    """Discover and browse DLNA media servers."""

    def __init__(
        self,
        discovery: DlnaDiscovery | None = None,
        client: DlnaClient | None = None,
        playback: DlnaPlaybackService | None = None,
        cache_ttl: float = 60.0,
        missing_ttl: float = 3.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.discovery = discovery or DlnaDiscovery()
        self.client = client or DlnaClient()
        self.playback = playback or DlnaPlaybackService()
        self.subscriptions = DlnaEventSubscriptions(self.playback.renderer)
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

    async def get_server(self, server_id: str) -> DlnaServer:
        """Resolve a discovered server using the shared cache."""
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

    async def browse(self, server_id: str, object_id: str = "0") -> list[DlnaItem]:
        """Browse a cached server without repeated SSDP searches."""
        server = await self.get_server(server_id)
        return await self.client.browse(server, object_id)

    async def play(
        self,
        device_id: str,
        device_ip: str,
        server_id: str,
        parent_id: str,
        object_id: str,
        callback_base_url: str | None,
    ) -> DlnaItem:
        """Play a DLNA item, creating a queue from its parent container."""
        items = await self.browse(server_id, parent_id)
        if callback_base_url is not None:
            callback_url = (
                f"{callback_base_url.rstrip('/')}/api/dlna/events/{device_id}"
            )
            try:
                await self.subscriptions.ensure(
                    device_id=device_id,
                    device_ip=device_ip,
                    callback_url=callback_url,
                )
            except Exception:
                logger.warning(
                    "DLNA subscription failed; playing without auto-advance: device=%s",
                    device_id,
                    exc_info=True,
                )
        return await self.playback.play(
            device_id=device_id,
            device_ip=device_ip,
            server_id=server_id,
            items=items,
            object_id=object_id,
        )

    async def pause(self, device_id: str, device_ip: str) -> None:
        await self.playback.pause(device_id, device_ip)

    async def resume(self, device_id: str, device_ip: str) -> None:
        await self.playback.resume(device_id, device_ip)

    async def next(self, device_id: str, device_ip: str) -> DlnaItem:
        return await self.playback.next(device_id, device_ip)

    async def previous(self, device_id: str, device_ip: str) -> DlnaItem:
        return await self.playback.previous(device_id, device_ip)

    async def close(self) -> None:
        """Stop playback and release AVTransport subscriptions."""
        await self.playback.close()
        await self.subscriptions.close()
