"""Live availability of media servers registered on a speaker (no caching, decision 7)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from enum import Enum

from defusedxml import ElementTree

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    raise_coded,
)
from opencloudtouch.devices.adapter import get_device_client
from opencloudtouch.devices.client import DeviceClient
from opencloudtouch.devices.repository import Device, DeviceRepository
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT
from opencloudtouch.marge.source_repository import MargeSourceRepository
from opencloudtouch.migrations.service import SpeakerMigrationService
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import fetch_device_presets

logger = logging.getLogger(__name__)


class NativeState(str, Enum):
    NOT_ENABLED = "not_enabled"
    READY = "ready"
    UNAVAILABLE = "unavailable"


def _default_client(device: Device) -> DeviceClient:
    return get_device_client(
        f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR - LAN HTTP only
    )


def _speaker_spelling(server_id: str, known: list[str]) -> str:
    """The speaker's spelling of a UDN (decision 48); the given id if unknown."""
    return next((u for u in known if u.lower() == server_id.lower()), server_id)


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
        migration_service: SpeakerMigrationService | None = None,
        presets_xml: Callable[[str], Awaitable[bytes]] = fetch_device_presets,
        preset_repo: PresetRepository | None = None,
    ):
        self._source_repo = source_repo
        self._device_repo = device_repo
        self._client_factory = client_factory
        self._sleep = sleep
        self._poll_interval = poll_interval
        self._ready_timeout = ready_timeout
        self._migrations = migration_service
        self._presets_xml = presets_xml
        # Mock mode only: mock speakers have no /presets, so the OCT rows stand in.
        self._preset_repo = preset_repo

    async def read_state(self, device_id: str, server_id: str) -> NativeState:
        states = await self._read(device_id, server_id)
        return next(iter(states.values()), NativeState.NOT_ENABLED)

    async def read_states(self, device_id: str) -> dict[str, NativeState]:
        """States of all registered servers, keyed by the speaker's UDN spelling."""
        return await self._read(device_id, None)

    async def display_names(self, device_id: str) -> dict[str, str]:
        """The speaker's names of its media servers, keyed by lower-case UDN."""
        client = self._client_factory(await self._device(device_id))
        try:
            sources = await client.get_source_list()
        except DeviceConnectionError:
            return {}
        finally:
            await client.close()
        return {
            s.account[:-2].lower(): s.display_name
            for s in sources
            if s.source == "STORED_MUSIC"
            and s.account.endswith("/0")
            and len(s.account) > 2
            and s.display_name
        }

    async def enable(self, device_id: str, server_id: str, name: str) -> NativeState:
        """Register a server through the speaker's own account call (decision 10)."""
        if self._migrations is not None:
            _, last_error = await self._migrations.status(device_id)
            if last_error:
                raise_coded(
                    409,
                    error_codes.DLNA_MIGRATION_FAILED,
                    "The speaker migration failed; media servers are disabled",
                    extra={"reason": last_error},
                )
        if await self.read_state(device_id, server_id) is NativeState.READY:
            return NativeState.READY
        client = self._client_factory(await self._device(device_id))
        try:
            udn = _speaker_spelling(server_id, await client.list_media_servers())
            try:
                await client.register_media_server(udn, name)
            except DeviceConnectionError as e:
                # 1022: the speaker's Marge account is empty, so a retry never helps.
                if "error 1022:" not in str(e):
                    raise
                raise_coded(
                    409,
                    error_codes.DLNA_SPEAKER_NO_ACCOUNT,
                    "Speaker has no OCT account; finish the speaker setup first",
                )
            # No re-register and no re-pair loop: waiting is all that can help.
            waited = 0.0
            while udn.lower() not in await self._listed(client):
                if waited >= self._ready_timeout:
                    break
                await self._sleep(self._poll_interval)
                waited += self._poll_interval
        finally:
            await client.close()
        return await self.read_state(device_id, udn)

    async def remove(self, device_id: str, server_id: str, force: bool = False) -> None:
        """Remove a server from the speaker; presets are never rewritten (decision 29)."""
        device = await self._device(device_id)
        if not force:
            slots = await self._slots(device, server_id)
            if slots:
                raise_coded(
                    409,
                    error_codes.DLNA_NATIVE_SLOTS_AFFECTED,
                    "Presets use this server",
                    extra={"slots": slots},
                )
        client = self._client_factory(device)
        try:
            accounts = [
                s.account[:-2]
                for s in await client.get_source_list()
                if s.source == "STORED_MUSIC" and s.account.endswith("/0")
            ]
            await client.remove_media_server(_speaker_spelling(server_id, accounts))
            # The speaker's DELETE callback normally removes the row; this is idempotent.
            account = device.marge_account_uuid
            deleted = False
            for row in (
                await self._source_repo.list_for_account(account) if account else []
            ):
                if row.server_id.lower() == server_id.lower() and (
                    await self._source_repo.delete(row.account_id, row.source_id)
                ):
                    deleted = True
            if deleted:  # no callback (1047): the speaker only syncs on a push (T21)
                await client.notify_sources_updated(device.device_id)
        finally:
            await client.close()

    async def _slots(self, device: Device, server_id: str) -> list[int]:
        account = f"{server_id}/0".lower()
        if self._preset_repo is not None:
            return [
                p.preset_number
                for p in await self._preset_repo.get_all_presets(device.device_id)
                if p.source == "STORED_MUSIC"
                and (p.source_account or "").lower() == account
            ]
        root = ElementTree.fromstring(await self._presets_xml(device.ip))
        return [
            int(preset.get("id", "0"))
            for preset in root.iter("preset")
            if (item := preset.find("ContentItem")) is not None
            and item.get("source") == "STORED_MUSIC"
            and item.get("sourceAccount", "").lower() == account
        ]

    @staticmethod
    async def _listed(client: DeviceClient) -> set[str]:
        try:
            return {u.lower() for u in await client.list_media_servers()}
        except DeviceConnectionError:
            return set()

    async def _device(self, device_id: str) -> Device:
        device = await self._device_repo.get_by_device_id(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        return device

    async def _read(self, device_id: str, only: str | None) -> dict[str, NativeState]:
        device = await self._device(device_id)
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
