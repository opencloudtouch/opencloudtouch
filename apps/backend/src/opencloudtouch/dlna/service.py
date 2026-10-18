"""DLNA application service."""

import asyncio
import time
from collections.abc import Callable

from opencloudtouch.dlna.client import DlnaClient
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.events import DlnaEventSubscriptions
from opencloudtouch.dlna.playback import DlnaPlaybackService
from opencloudtouch.dlna.models import DlnaItem, DlnaServer


class DlnaService:
    """Discover and browse DLNA media servers."""

    def __init__(
        self,
        discovery: DlnaDiscovery | None = None,
        client: DlnaClient | None = None,
        playback: DlnaPlaybackService | None = None,
        cache_ttl: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.discovery = discovery or DlnaDiscovery()
        self.client = client or DlnaClient()
        self.playback = playback or DlnaPlaybackService()
        self.subscriptions = DlnaEventSubscriptions(self.playback.renderer)
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

    async def get_server(self, server_id: str) -> DlnaServer:
        """Resolve a discovered server using the shared cache."""
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
        callback_base_url: str,
    ) -> DlnaItem:
        """Play a DLNA item, creating a queue from its parent container."""
        items = await self.browse(server_id, parent_id)
        callback_url = f"{callback_base_url.rstrip('/')}/api/dlna/events/{device_id}"
        await self.subscriptions.ensure(
            device_id=device_id,
            device_ip=device_ip,
            callback_url=callback_url,
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
