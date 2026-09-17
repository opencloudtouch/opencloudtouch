"""DLNA application service."""

from opencloudtouch.dlna.client import DlnaClient
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.models import DlnaItem, DlnaServer


class DlnaService:
    """Discover and browse DLNA media servers."""

    def __init__(
        self,
        discovery: DlnaDiscovery | None = None,
        client: DlnaClient | None = None,
    ):
        self.discovery = discovery or DlnaDiscovery()
        self.client = client or DlnaClient()

    async def get_servers(self) -> list[DlnaServer]:
        """Discover available DLNA media servers."""
        return await self.discovery.discover()

    async def browse(
        self,
        server_id: str,
        object_id: str = "0",
    ) -> list[DlnaItem]:
        """Browse a media server by its discovered server ID."""
        servers = await self.discovery.discover()

        server = next(
            (server for server in servers if server.id == server_id),
            None,
        )

        if server is None:
            raise LookupError(f"DLNA server not found: {server_id}")

        return await self.client.browse(server, object_id)
