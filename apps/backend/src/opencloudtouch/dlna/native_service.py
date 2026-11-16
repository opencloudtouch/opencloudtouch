"""Registration of DLNA media servers as native STORED_MUSIC sources on a speaker.

The state of a (speaker, server) pair is derived from OpenCloudTouch's row (written by
the speaker's own Marge callback) and the speaker's live ``/sources`` list. The service
never restarts a speaker and never re-registers an account the speaker lists.
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
STALE_PROVIDER_ID = 50  # the speaker cached OpenCloudTouch's old provider list
UNKNOWN_ACCOUNT = 1047  # removeMusicServiceAccount of an account the speaker lacks
DISPLAY_NAME_MAX = 64
SPEAKER_PORT = 8090


class NativeState(str, Enum):
    NOT_REGISTERED = "not_registered"
    UNMANAGED = "unmanaged"
    RESTART_REQUIRED = "restart_required"
    READY = "ready"
    UNAVAILABLE = "unavailable"
    REMOVAL_PENDING = "removal_pending"


class NativeSourceRow(Protocol):
    """A registration row (implemented by ``marge.MargeSourceRepository``)."""

    @property
    def source_id(self) -> int: ...
    @property
    def server_id(self) -> str: ...
    @property
    def display_name(self) -> str: ...
    @property
    def removal_pending(self) -> bool: ...
    @property
    def received_provider_id(self) -> int: ...


class NativeSourceStore(Protocol):
    async def get_by_server(
        self, device_id: str, server_id: str
    ) -> NativeSourceRow | None: ...
    async def list_for_device(self, device_id: str) -> Sequence[NativeSourceRow]: ...
    async def upsert(
        self,
        device_id: str,
        server_id: str,
        display_name: str,
        received_provider_id: int,
    ) -> NativeSourceRow: ...
    async def delete(self, device_id: str, server_id: str) -> None: ...
    async def mark_removal_pending(self, device_id: str, source_id: int) -> None: ...


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


@dataclass(frozen=True)
class EnableResult:
    state: NativeState
    created: bool  # True: a registration was made now (HTTP 202), else 200


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


def derive_state(
    row: NativeSourceRow | None, listed: SpeakerSource | None
) -> NativeState:
    """State table of the spec (Decision 7) with Amendment 1."""
    if row is None:
        return NativeState.UNMANAGED if listed else NativeState.NOT_REGISTERED
    if row.removal_pending:
        return NativeState.REMOVAL_PENDING if listed else NativeState.NOT_REGISTERED
    if listed:
        return (
            NativeState.READY
            if listed.status.upper() == "READY"
            else NativeState.UNAVAILABLE
        )
    if row.received_provider_id == STALE_PROVIDER_ID:
        return NativeState.RESTART_REQUIRED
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
        row_polls: int = 10,
        poll_interval: float = 0.5,
        ready_timeout: float = 30.0,
    ):
        self._store = store
        self._devices = device_repository
        self._dlna = dlna_service
        self._presets = preset_store
        self._client_factory = client_factory
        self._row_polls = row_polls
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

    async def _sources(self, client: DeviceClient) -> list[SpeakerSource]:
        return await client.get_source_list()  # DeviceConnectionError -> 503

    async def _find_server(self, server_id: str) -> DlnaServer | None:
        for server in await self._dlna.list_servers():
            if server.id.lower() == server_id.lower():
                return server
        return None

    # ---- read -----------------------------------------------------------------------

    async def state(self, device_id: str) -> list[NativeServerState]:
        """Every discovered server and every registration row, with its state."""
        device = await self._device(device_id)
        client = self._client_factory(device)
        try:
            sources = await self._sources(client)
        finally:
            await client.close()
        rows = {r.server_id: r for r in await self._store.list_for_device(device_id)}
        known = {s.id.lower(): s for s in await self._dlna.list_servers()}
        result = []
        for server_id in [*known, *(r for r in rows if r not in known)]:
            row = rows.get(server_id)
            state = derive_state(row, _listed(sources, server_id))
            if (
                row is not None
                and row.removal_pending
                and state is NativeState.NOT_REGISTERED
            ):
                await self._store.delete(device_id, server_id)  # removal took effect
                row = None
            server = known.get(server_id)
            result.append(
                NativeServerState(
                    server_id=server_id,
                    name=(
                        server.name
                        if server
                        else (row.display_name if row else server_id)
                    ),
                    state=state,
                    server_known=server is not None,
                    source_id=row.source_id if row else None,
                )
            )
        return result

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

    async def enable(self, device_id: str, server_id: str) -> EnableResult:
        device = await self._device(device_id)
        server = await self._find_server(server_id)
        if server is None:
            raise_coded(404, error_codes.DLNA_SERVER_NOT_FOUND, "DLNA server not found")
        sid = server.id.lower()
        if server_id_from_account(f"{sid}/0") is None:
            raise_coded(
                422,
                error_codes.VALIDATION_ERROR,
                "The media server id is not a UUID and cannot be registered",
                field="server_id",
            )
        async with self._lock(device_id, sid):
            client = self._client_factory(device)
            try:
                return await self._enable_locked(client, device_id, sid, server)
            finally:
                await client.close()

    async def _enable_locked(
        self, client: DeviceClient, device_id: str, sid: str, server: DlnaServer
    ) -> EnableResult:
        sources = await self._sources(client)
        row = await self._store.get_by_server(device_id, sid)
        state = derive_state(row, _listed(sources, sid))
        if state is NativeState.UNMANAGED:
            # Adopt: the speaker keeps its account, so it must not be registered again.
            adopted = await self._store.upsert(
                device_id, sid, server.name[:DISPLAY_NAME_MAX] or sid, 7
            )
            return EnableResult(derive_state(adopted, _listed(sources, sid)), False)
        if state in (NativeState.READY, NativeState.RESTART_REQUIRED):
            return EnableResult(state, False)
        if state is NativeState.UNAVAILABLE:
            raise_coded(
                409,
                error_codes.DLNA_NATIVE_ALREADY_REGISTERED,
                "The media server is registered but not usable; remove it and register again",
            )
        if state is NativeState.REMOVAL_PENDING:
            raise_coded(
                409,
                error_codes.DLNA_NATIVE_REMOVAL_PENDING,
                "The removal finishes with a speaker restart",
            )
        if row is not None:  # pending row of a finished removal: the read below deletes
            await self._store.delete(device_id, sid)
        return await self._register(client, device_id, sid, server)

    def _registration_failed(self) -> None:
        raise_coded(
            502,
            error_codes.DLNA_NATIVE_REGISTRATION_FAILED,
            "The speaker did not register the media server",
        )

    async def _register(
        self, client: DeviceClient, device_id: str, sid: str, server: DlnaServer
    ) -> EnableResult:
        name = (server.name.strip() or sid)[:DISPLAY_NAME_MAX]
        failed = False
        try:
            await client.set_music_service_account(SOURCE, name, f"{sid}/0")
        except SpeakerCommandError:
            failed = True
        except DeviceConnectionError:
            await self._store.delete(device_id, sid)  # created by this request
            raise
        row = None
        for attempt in range(self._row_polls):
            if failed:
                break
            row = await self._store.get_by_server(device_id, sid)
            if row is not None:
                break
            if attempt < self._row_polls - 1:
                await asyncio.sleep(self._poll_interval)
        if failed or row is None:
            await self._store.delete(device_id, sid)  # only a row this request created
            self._registration_failed()
        assert row is not None
        state = await self._await_listing(client, row, sid)
        return EnableResult(state, True)

    async def _await_listing(
        self, client: DeviceClient, row: NativeSourceRow, sid: str
    ) -> NativeState:
        """Poll the live source list until the account is READY (or the budget is used)."""
        if row.received_provider_id == STALE_PROVIDER_ID:
            return (
                NativeState.RESTART_REQUIRED
            )  # needs the one-time restart, no polling
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._ready_timeout
        listed = None
        while True:
            try:
                listed = _listed(await client.get_source_list(), sid)
            except DeviceConnectionError:
                logger.debug("Source list not readable while waiting for %s", sid)
            if (listed and listed.status.upper() == "READY") or loop.time() >= deadline:
                break
            await asyncio.sleep(self._poll_interval)
        return derive_state(row, listed)

    # ---- disable --------------------------------------------------------------------

    async def disable(
        self, device_id: str, server_id: str, force: bool = False
    ) -> list[int]:
        """Remove the registration; returns the slots that were switched back to v1."""
        device = await self._device(device_id)
        sid = server_id.lower()
        async with self._lock(device_id, sid):
            slots = await self.affected_slots(device_id, sid)
            if slots and not force:
                raise_coded(
                    409,
                    error_codes.DLNA_NATIVE_IN_USE,
                    "Native presets use this registration",
                    params={"slots": ",".join(str(p.preset_number) for p in slots)},
                )
            client = self._client_factory(device)
            try:
                return await self._disable_locked(client, device_id, sid, slots)
            finally:
                await client.close()

    async def _disable_locked(
        self,
        client: DeviceClient,
        device_id: str,
        sid: str,
        slots: "list[Preset]",
    ) -> list[int]:
        row = await self._store.get_by_server(device_id, sid)
        if row is None and _listed(await self._sources(client), sid) is None:
            return []
        await self._rewrite_to_v1(client, device_id, slots)
        name = row.display_name if row else sid
        try:
            await client.remove_music_service_account(SOURCE, name, f"{sid}/0")
        except SpeakerCommandError as exc:
            if exc.error_code != UNKNOWN_ACCOUNT:
                raise_coded(
                    502,
                    error_codes.DLNA_NATIVE_REMOVE_FAILED,
                    "The speaker did not remove the media server",
                )
        if row is not None:
            if _listed(await self._sources(client), sid):
                await self._store.mark_removal_pending(device_id, row.source_id)
            else:
                await self._store.delete(device_id, sid)
        return [p.preset_number for p in slots]

    async def _rewrite_to_v1(
        self, client: DeviceClient, device_id: str, slots: "list[Preset]"
    ) -> None:
        if not slots:
            return
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
