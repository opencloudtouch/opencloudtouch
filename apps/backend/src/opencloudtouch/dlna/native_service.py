"""Live availability of media servers registered on a speaker (no caching, decision 7)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from enum import Enum

from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.devices.adapter import get_device_client
from opencloudtouch.devices.client import DeviceClient
from opencloudtouch.devices.repository import Device, DeviceRepository
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT
from opencloudtouch.marge.source_repository import MargeSourceRepository

logger = logging.getLogger(__name__)


class NativeState(str, Enum):
    NOT_ENABLED = "not_enabled"
    READY = "ready"
    UNAVAILABLE = "unavailable"


def _default_client(device: Device) -> DeviceClient:
    return get_device_client(
        f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR - LAN HTTP only
    )


class DlnaNativeService:
    """Read the state of a speaker's media servers live from the speaker."""

    def __init__(
        self,
        source_repo: MargeSourceRepository,
        device_repo: DeviceRepository,
        client_factory: Callable[[Device], DeviceClient] = _default_client,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        poll_interval: float = 0.5,
        ready_timeout: float = 15.0,
    ):
        self._source_repo = source_repo
        self._device_repo = device_repo
        self._client_factory = client_factory
        self._sleep = sleep
        self._poll_interval = poll_interval
        self._ready_timeout = ready_timeout

    async def read_state(self, device_id: str, server_id: str) -> NativeState:
        states = await self._read(device_id, server_id)
        return next(iter(states.values()), NativeState.NOT_ENABLED)

    async def read_states(self, device_id: str) -> dict[str, NativeState]:
        """States of all registered servers, keyed by the speaker's UDN spelling."""
        return await self._read(device_id, None)

    async def _read(self, device_id: str, only: str | None) -> dict[str, NativeState]:
        device = await self._device_repo.get_by_device_id(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        account = device.marge_account_uuid
        rows = await self._source_repo.list_for_account(account) if account else []
        client = self._client_factory(device)
        try:
            return await self._states(client, [r.server_id for r in rows], only)
        finally:
            await client.close()

    async def _states(
        self, client: DeviceClient, row_ids: list[str], only: str | None
    ) -> dict[str, NativeState]:
        try:
            sources = [
                s
                for s in await client.get_source_list()
                if s.source == "STORED_MUSIC"
                and s.account.endswith("/0")
                and len(s.account) > 2  # empty-account placeholders (T15)
            ]
        except DeviceConnectionError:
            sources = None
        # Registered = OCT row or speaker entry; the speaker's spelling wins (decision 48).
        udns: dict[str, str] = {}
        for udn in [s.account[:-2] for s in sources or []] + row_ids:
            udns.setdefault(udn.lower(), udn)
        if only is not None:
            udns = {k: v for k, v in udns.items() if k == only.lower()}
        if sources is None:
            return {udn: NativeState.UNAVAILABLE for udn in udns.values()}
        ready = {s.account[:-2].lower() for s in sources if s.status.upper() == "READY"}
        listed: set[str] | None = None
        listed_read = False
        result = {}
        for key, udn in udns.items():
            if key not in ready:
                result[udn] = NativeState.UNAVAILABLE
                continue
            if not listed_read:
                listed_read = True
                try:
                    listed = {u.lower() for u in await client.list_media_servers()}
                except DeviceConnectionError:
                    logger.warning("listMediaServers failed; relying on browse result")
            if listed is not None and key not in listed:
                result[udn] = NativeState.UNAVAILABLE
                continue
            try:
                browse = await client.browse_stored_music(f"{udn}/0")
            except DeviceConnectionError:
                result[udn] = NativeState.UNAVAILABLE
                continue
            # 1602 is retried once in the client (task 3); any other code is final.
            result[udn] = (
                NativeState.UNAVAILABLE if browse.error_code else NativeState.READY
            )
        return result
