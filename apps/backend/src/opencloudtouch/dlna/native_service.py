"""Enabling DLNA media servers as native STORED_MUSIC sources of a speaker.

OpenCloudTouch itself lists the enabled servers in the Marge account document
(``/streaming/account/{id}/full``); the speaker takes them from there. The state of a
(speaker, server) pair is derived from OpenCloudTouch's row and the speaker's live
``/sources`` list. A speaker that still caches an old provider list is re-paired once
(``setMargeAccount``) so that it reads the account document again; it is never restarted.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

from opencloudtouch.core import error_codes
from opencloudtouch.core.dlna_reference import (
    DlnaReference,
    from_station_url,
    server_id_from_account,
)
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    raise_coded,
)
from opencloudtouch.devices.client import (
    DeviceClient,
    SpeakerCommandError,
    SpeakerSource,
)
from opencloudtouch.dlna.models import DlnaServer

if TYPE_CHECKING:
    from opencloudtouch.presets.models import Preset

logger = logging.getLogger(__name__)

SOURCE = "STORED_MUSIC"
DISPLAY_NAME_MAX = 64
SPEAKER_PORT = 8090


class NativeState(str, Enum):
    NOT_ENABLED = "not_enabled"
    READY = "ready"
    UNAVAILABLE = "unavailable"


class NativeSourceRow(Protocol):
    """A row of an enabled server (implemented by ``marge.MargeSourceRepository``)."""

    @property
    def source_id(self) -> int: ...
    @property
    def server_id(self) -> str: ...
    @property
    def display_name(self) -> str: ...


class NativeSourceStore(Protocol):
    async def get_by_server(
        self, device_id: str, server_id: str
    ) -> NativeSourceRow | None: ...
    async def list_active(self, device_id: str) -> Sequence[NativeSourceRow]: ...
    async def upsert(
        self, device_id: str, server_id: str, display_name: str
    ) -> NativeSourceRow: ...
    async def delete(self, device_id: str, server_id: str) -> None: ...


class PresetStore(Protocol):
    async def get_all_presets(self, device_id: str) -> "list[Preset]": ...
    async def set_preset(self, preset: "Preset") -> Any: ...


@dataclass(frozen=True)
class NativeServerState:
    server_id: str
    name: str
    state: NativeState
    server_known: bool
    source_id: int | None


def _default_client(device: Any) -> DeviceClient:
    from opencloudtouch.devices.adapter import get_device_client

    return get_device_client(
        f"http://{device.ip}:{SPEAKER_PORT}"
    )  # NOSONAR - LAN speaker


def _listed(sources: Sequence[SpeakerSource], server_id: str) -> SpeakerSource | None:
    account = f"{server_id}/0".lower()
    for entry in sources:
        if entry.source == SOURCE and entry.account.lower() == account:
            return entry
    return None


def _is_ready(sources: Sequence[SpeakerSource], server_id: str) -> bool:
    listed = _listed(sources, server_id)
    return listed is not None and listed.status.upper() == "READY"


def derive_state(
    row: NativeSourceRow | None, listed: SpeakerSource | None
) -> NativeState:
    """No row: not enabled (a listing without a row goes away with the next sync)."""
    if row is None:
        return NativeState.NOT_ENABLED
    if listed is not None and listed.status.upper() == "READY":
        return NativeState.READY
    return NativeState.UNAVAILABLE


class DlnaNativeService:
    """Enable, inspect and disable native playback of a media server on one speaker."""

    def __init__(
        self,
        store: NativeSourceStore,
        device_repository: Any,
        dlna_service: Any,
        preset_store: PresetStore,
        client_factory: Callable[[Any], DeviceClient] = _default_client,
        poll_interval: float = 0.5,
        ready_timeout: float = 15.0,
    ):
        self._store = store
        self._devices = device_repository
        self._dlna = dlna_service
        self._presets = preset_store
        self._client_factory = client_factory
        self._poll_interval = poll_interval
        self._ready_timeout = ready_timeout
        # shortcut: one process only (single backend), a distributed lock is not needed
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    def _lock(self, device_id: str, server_id: str) -> asyncio.Lock:
        return self._locks.setdefault((device_id, server_id), asyncio.Lock())

    async def _device(self, device_id: str) -> Any:
        device = await self._devices.get_by_device_id(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        return device

    async def _find_server(self, server_id: str) -> DlnaServer | None:
        for server in await self._dlna.list_servers():
            if server.id.lower() == server_id.lower():
                return server
        return None

    # ---- read -----------------------------------------------------------------------

    async def state(self, device_id: str) -> list[NativeServerState]:
        """Every discovered server and every enabled row, with its state."""
        device = await self._device(device_id)
        client = self._client_factory(device)
        try:
            sources = await client.get_source_list()  # DeviceConnectionError -> 503
        finally:
            await client.close()
        rows = {r.server_id: r for r in await self._store.list_active(device_id)}
        known = {s.id.lower(): s for s in await self._dlna.list_servers()}
        result = []
        for server_id in [*known, *(r for r in rows if r not in known)]:
            row = rows.get(server_id)
            server = known.get(server_id)
            result.append(
                NativeServerState(
                    server_id=server_id,
                    name=(
                        server.name
                        if server
                        else (row.display_name if row else server_id)
                    ),
                    state=derive_state(row, _listed(sources, server_id)),
                    server_known=server is not None,
                    source_id=row.source_id if row else None,
                )
            )
        return result

    async def native_ready(self, device_id: str, server_id: str) -> bool:
        """True when the server is enabled here and READY on the speaker's live list."""
        device = await self._device(device_id)
        client = self._client_factory(device)
        try:
            sources = await client.get_source_list()  # DeviceConnectionError -> caller
        finally:
            await client.close()
        sid = server_id.lower()
        row = await self._store.get_by_server(device_id, sid)
        return derive_state(row, _listed(sources, sid)) is NativeState.READY

    async def affected_slots(self, device_id: str, server_id: str) -> "list[Preset]":
        """Native presets of the device that use the server."""
        slots = []
        for preset in await self._presets.get_all_presets(device_id):
            ref = from_station_url(preset.station_url)
            if (
                preset.source == "DLNA"
                and preset.native_type
                and ref
                and ref.server_id.lower() == server_id.lower()
            ):
                slots.append(preset)
        return slots

    # ---- enable ---------------------------------------------------------------------

    async def enable(self, device_id: str, server_id: str) -> NativeState:
        device = await self._device(device_id)
        server = await self._find_server(server_id)
        if server is None:
            raise_coded(404, error_codes.DLNA_SERVER_NOT_FOUND, "DLNA server not found")
        sid = server.id.lower()
        if server_id_from_account(f"{sid}/0") is None:
            raise_coded(
                422,
                error_codes.VALIDATION_ERROR,
                "The media server id is not a UUID and cannot be used as a source",
                field="server_id",
            )
        async with self._lock(device_id, sid):
            client = self._client_factory(device)
            try:
                return await self._enable_locked(client, device, sid, server)
            finally:
                await client.close()

    async def _enable_locked(
        self, client: DeviceClient, device: Any, sid: str, server: DlnaServer
    ) -> NativeState:
        device_id = device.device_id
        existed = await self._store.get_by_server(device_id, sid) is not None
        await self._store.upsert(
            device_id, sid, (server.name.strip() or sid)[:DISPLAY_NAME_MAX]
        )
        try:
            if _is_ready(await client.get_source_list(), sid):
                return NativeState.READY
            # Not listed yet: one re-pairing makes the speaker read the account document.
            account_id = getattr(device, "marge_account_uuid", None) or device_id
            await client.pair_with_account(account_id)
        except (SpeakerCommandError, DeviceConnectionError) as exc:
            if not existed:  # only a row this request created
                await self._store.delete(device_id, sid)
            if isinstance(exc, DeviceConnectionError):
                raise
            raise_coded(
                502,
                error_codes.DLNA_NATIVE_SETUP_FAILED,
                "The speaker did not accept the pairing",
            )
        return await self._await_ready(client, sid)

    async def _await_ready(self, client: DeviceClient, sid: str) -> NativeState:
        """Poll the live source list until the account is READY or the budget is used."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._ready_timeout
        while True:
            try:
                if _is_ready(await client.get_source_list(), sid):
                    return NativeState.READY
            except DeviceConnectionError:
                logger.debug("Source list not readable while waiting for %s", sid)
            if loop.time() >= deadline:
                return NativeState.UNAVAILABLE
            await asyncio.sleep(self._poll_interval)

    # ---- disable --------------------------------------------------------------------

    async def disable(
        self, device_id: str, server_id: str, force: bool = False
    ) -> list[int]:
        """Stop listing the server; returns the slots that were switched back to v1.

        The speaker drops the source with its next account sync.
        """
        device = await self._device(device_id)
        sid = server_id.lower()
        async with self._lock(device_id, sid):
            slots = await self.affected_slots(device_id, sid)
            if slots and not force:
                raise_coded(
                    409,
                    error_codes.DLNA_NATIVE_IN_USE,
                    "Native presets use this media server",
                    params={"slots": ",".join(str(p.preset_number) for p in slots)},
                )
            if slots:
                client = self._client_factory(device)
                try:
                    await self._rewrite_to_v1(client, device_id, slots)
                finally:
                    await client.close()
            await self._store.delete(device_id, sid)
            return [p.preset_number for p in slots]

    async def _rewrite_to_v1(
        self, client: DeviceClient, device_id: str, slots: "list[Preset]"
    ) -> None:
        from opencloudtouch.core.config import get_config

        for preset in slots:
            ref = from_station_url(preset.station_url)
            assert isinstance(ref, DlnaReference)
            try:
                await client.store_preset(
                    device_id=device_id,
                    preset_number=preset.preset_number,
                    station_url=preset.station_url,
                    station_name=preset.station_name,
                    oct_backend_url=get_config().station_descriptor_base_url,
                    station_image_url=preset.station_favicon or "",
                    station_uuid=preset.station_uuid,
                    dlna_reference=ref,
                )
                preset.native_type = None
                await self._presets.set_preset(preset)
            except (DeviceConnectionError, ValueError):
                raise_coded(
                    502,
                    error_codes.DLNA_NATIVE_REMOVE_FAILED,
                    "A preset slot could not be switched back to first-track playback",
                )
