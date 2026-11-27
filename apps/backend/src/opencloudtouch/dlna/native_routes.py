"""Per-speaker media server routes; every state is read live from the speaker."""

from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from opencloudtouch.core import error_codes
from opencloudtouch.core.dependencies import (
    DlnaNativeServiceDep,
    DlnaServiceDep,
    SpeakerMigrationServiceDep,
)
from opencloudtouch.core.exceptions import raise_coded
from opencloudtouch.dlna.models import DlnaServer
from opencloudtouch.dlna.native_service import NativeState

router = APIRouter(prefix="/api/dlna/native", tags=["dlna"])


class NativeServer(BaseModel):
    server_id: str
    name: str
    state: Literal["not_enabled", "ready", "unavailable"]
    discovered: bool
    # Two servers on one host hide each other in the speaker (decision 22).
    host: str | None


class NativeServerList(BaseModel):
    servers: list[NativeServer]
    migration_failed: bool
    migration_reason: str | None


def _discovered(server: DlnaServer, state: NativeState) -> NativeServer:
    return NativeServer(
        server_id=server.id,
        name=server.name,
        state=state.value,
        discovered=True,
        host=urlparse(server.location).hostname,
    )


def _undiscovered(udn: str, state: NativeState) -> NativeServer:
    # shortcut: the UDN is the name, the speaker's displayName is not read here
    return NativeServer(
        server_id=udn, name=udn, state=state.value, discovered=False, host=None
    )


@router.get("", response_model=NativeServerList)
async def list_native_servers(
    native: DlnaNativeServiceDep,
    dlna: DlnaServiceDep,
    migrations: SpeakerMigrationServiceDep,
    device_id: str = Query(...),
    discover: bool = Query(default=True),
) -> NativeServerList:
    """Discovered servers plus registered ones, with live states (decision 32).

    ``discover=false`` skips the SSDP scan and uses the servers already known.
    """
    states = {
        k.lower(): (k, v) for k, v in (await native.read_states(device_id)).items()
    }
    servers = []
    known = await dlna.get_servers() if discover else dlna.known_servers()
    for server in known:
        _, state = states.pop(server.id.lower(), (None, NativeState.NOT_ENABLED))
        servers.append(_discovered(server, state))
    servers += [_undiscovered(udn, state) for udn, state in states.values()]
    _, last_error = await migrations.status(device_id)
    return NativeServerList(
        servers=servers,
        migration_failed=last_error is not None,
        migration_reason=last_error,
    )


@router.put("/{device_id}/servers/{server_id}", response_model=NativeServer)
async def enable_native_server(
    device_id: str,
    server_id: str,
    native: DlnaNativeServiceDep,
    dlna: DlnaServiceDep,
) -> NativeServer:
    """Register a server on the speaker; UNAVAILABLE is a state, not an error."""
    found = next(
        (s for s in await dlna.get_servers() if s.id.lower() == server_id.lower()),
        None,
    )
    if found is not None:
        return _discovered(found, await native.enable(device_id, found.id, found.name))
    # Not discovered: only an already registered server may be enabled again.
    udn = next(
        (
            u
            for u in await native.read_states(device_id)
            if u.lower() == server_id.lower()
        ),
        None,
    )
    if udn is None:
        raise_coded(
            404, error_codes.DLNA_SERVER_NOT_FOUND, f"Unknown server {server_id}"
        )
    return _undiscovered(udn, await native.enable(device_id, udn, udn))


@router.delete("/{device_id}/servers/{server_id}", status_code=204)
async def remove_native_server(
    device_id: str,
    server_id: str,
    native: DlnaNativeServiceDep,
    force: bool = Query(default=False),
) -> Response:
    """Remove a server; 409 with the live slot list unless ``force`` (decision 29)."""
    await native.remove(device_id, server_id, force)
    return Response(status_code=204)
