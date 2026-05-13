"""Zone service for multi-room management."""

import asyncio
import logging
from typing import TYPE_CHECKING, Callable

from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT
from opencloudtouch.zones.models import ZoneMemberInfo, ZoneStatus

if TYPE_CHECKING:
    from opencloudtouch.devices.client import DeviceClient

logger = logging.getLogger(__name__)

# Type alias for the client factory function
DeviceClientFactory = Callable[[str], "DeviceClient"]


class ZoneService:
    """Service for managing multi-room zones."""

    def __init__(
        self,
        device_repo: DeviceRepository,
        client_factory: DeviceClientFactory | None = None,
    ) -> None:
        self.device_repo = device_repo
        self._client_factory = client_factory

    def _get_client(self, ip: str) -> "DeviceClient":
        """Get a device client for the given IP via injected factory."""
        if self._client_factory is None:
            # Fallback: lazy import (backward compat during transition)
            from opencloudtouch.devices.adapter import get_device_client

            return get_device_client(
                f"http://{ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR — Bose devices only support HTTP
            )
        return self._client_factory(
            f"http://{ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR — Bose devices only support HTTP
        )

    async def _get_device_or_raise(self, device_id: str):
        """Get device from repo or raise DeviceNotFoundError."""
        device = await self.device_repo.get_by_device_id(device_id)
        if not device:
            raise DeviceNotFoundError(device_id)
        return device

    def _enrich_zone_status(self, status: ZoneStatus, devices: list) -> ZoneStatus:
        """Enrich zone members with name/model from device list."""
        device_map = {d.device_id: d for d in devices}
        enriched_members = []
        for member in status.members:
            device = device_map.get(member.device_id)
            enriched_members.append(
                ZoneMemberInfo(
                    device_id=member.device_id,
                    ip_address=member.ip_address,
                    role=member.role,
                    name=device.name if device else member.name,
                    model=device.model if device else member.model,
                )
            )
        return ZoneStatus(
            master_id=status.master_id,
            master_ip=status.master_ip,
            is_master=status.is_master,
            members=enriched_members,
        )

    async def get_zone_status(self, device_id: str) -> ZoneStatus | None:
        """Get zone status for a specific device."""
        device = await self._get_device_or_raise(device_id)
        client = self._get_client(device.ip)
        try:
            status = await client.get_zone_status()
        except Exception as e:
            raise DeviceConnectionError(device.ip, str(e))
        if not status:
            return None
        devices = await self.device_repo.get_all()
        return self._enrich_zone_status(status, devices)

    async def get_all_zones(self) -> list[ZoneStatus]:
        """Get all active zones across all devices."""
        devices = await self.device_repo.get_all()
        if not devices:
            return []

        async def _fetch_zone(device):
            try:
                client = self._get_client(device.ip)
                status = await client.get_zone_status()
                if status:
                    logger.debug(
                        "Zone from %s (is_master=%s): master=%s, members=%d [%s]",
                        device.device_id,
                        status.is_master,
                        status.master_id,
                        len(status.members),
                        ", ".join(m.device_id for m in status.members),
                    )
                return status
            except Exception:
                logger.debug("Could not get zone for %s: skipped", device.device_id)
                return None

        results = await asyncio.gather(*[_fetch_zone(d) for d in devices])

        # Group zone results by master_id, preferring the master's own
        # perspective (is_master=True) since it has the complete member list.
        zone_map: dict[str, ZoneStatus] = {}
        for status in results:
            if not status:
                continue
            mid = status.master_id
            if mid not in zone_map or (
                status.is_master and not zone_map[mid].is_master
            ):
                zone_map[mid] = status

        zones: list[ZoneStatus] = [
            self._enrich_zone_status(s, devices) for s in zone_map.values()
        ]
        logger.info(
            "get_all_zones: %d zone(s), members: %s",
            len(zones),
            {z.master_id: len(z.members) for z in zones},
        )
        return zones

    async def create_zone(self, master_id: str, slave_ids: list[str]) -> ZoneStatus:
        """Create a new multi-room zone."""
        logger.info("Creating zone: master=%s, slaves=%s", master_id, slave_ids)
        master = await self._get_device_or_raise(master_id)
        slaves = []
        for sid in slave_ids:
            slave = await self._get_device_or_raise(sid)
            slaves.append(slave)

        members = [
            ZoneMemberInfo(device_id=s.device_id, ip_address=s.ip, role="slave")
            for s in slaves
        ]

        client = self._get_client(master.ip)
        try:
            status = await client.create_zone(master.ip, members)
        except Exception as e:
            logger.error("Failed to create zone master=%s: %s", master_id, e)
            raise DeviceConnectionError(master.ip, str(e))

        logger.info(
            "Zone created: master=%s, members=%d [%s]",
            master_id,
            len(status.members),
            ", ".join(m.device_id for m in status.members),
        )
        devices = await self.device_repo.get_all()
        return self._enrich_zone_status(status, devices)

    async def add_members(self, master_id: str, slave_ids: list[str]) -> None:
        """Add members to an existing zone."""
        master = await self._get_device_or_raise(master_id)
        slaves = []
        for sid in slave_ids:
            slave = await self._get_device_or_raise(sid)
            slaves.append(slave)

        members = [
            ZoneMemberInfo(device_id=s.device_id, ip_address=s.ip, role="slave")
            for s in slaves
        ]

        client = self._get_client(master.ip)
        try:
            await client.add_zone_members(members)
        except Exception as e:
            raise DeviceConnectionError(master.ip, str(e))

    async def remove_members(self, master_id: str, slave_ids: list[str]) -> None:
        """Remove members from an existing zone."""
        master = await self._get_device_or_raise(master_id)
        slaves = []
        for sid in slave_ids:
            slave = await self._get_device_or_raise(sid)
            slaves.append(slave)

        members = [
            ZoneMemberInfo(device_id=s.device_id, ip_address=s.ip, role="slave")
            for s in slaves
        ]

        client = self._get_client(master.ip)
        try:
            await client.remove_zone_members(members)
        except Exception as e:
            raise DeviceConnectionError(master.ip, str(e))

    async def dissolve_zone(self, master_id: str) -> None:
        """Dissolve an existing zone."""
        logger.info("Dissolving zone with master_id=%s", master_id)
        master = await self._get_device_or_raise(master_id)
        client = self._get_client(master.ip)
        try:
            await client.remove_zone()
            logger.info("Zone dissolved successfully for master_id=%s", master_id)
        except Exception as e:
            logger.error("Failed to dissolve zone master_id=%s: %s", master_id, e)
            raise DeviceConnectionError(master.ip, str(e))

    async def change_master(self, old_master_id: str, new_master_id: str) -> ZoneStatus:
        """Change the master of a zone. Dissolve old, recreate with new master."""
        old_master = await self._get_device_or_raise(old_master_id)
        await self._get_device_or_raise(new_master_id)  # validate exists

        # Get current zone to know members
        client = self._get_client(old_master.ip)
        try:
            current_zone = await client.get_zone_status()
        except Exception as e:
            raise DeviceConnectionError(old_master.ip, str(e))

        if not current_zone:
            raise ValueError(f"Device {old_master_id} is not in a zone")

        # Collect all member IDs except the new master
        other_ids = [
            m.device_id for m in current_zone.members if m.device_id != new_master_id
        ]

        # Dissolve old zone
        try:
            await client.remove_zone()
        except Exception as e:
            raise DeviceConnectionError(old_master.ip, str(e))

        # Create new zone with new master
        try:
            return await self.create_zone(new_master_id, other_ids)
        except Exception:
            # Rollback: try to recreate original zone
            try:
                original_slave_ids = [
                    m.device_id
                    for m in current_zone.members
                    if m.device_id != old_master_id
                ]
                await self.create_zone(old_master_id, original_slave_ids)
            except Exception:
                logger.error("Rollback failed during change_master")
            raise
