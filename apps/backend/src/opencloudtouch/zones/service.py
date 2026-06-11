"""Zone service for multi-room management."""

import asyncio
import logging
from typing import TYPE_CHECKING, Callable

from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT
from opencloudtouch.zones.models import ZoneMemberInfo, ZoneStatus
from opencloudtouch.zones.repository import ZoneRepository

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
        zone_repo: ZoneRepository,
        client_factory: DeviceClientFactory | None = None,
    ) -> None:
        self.device_repo = device_repo
        self.zone_repo = zone_repo
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
        status = await client.get_zone_status()
        if not status:
            return None
        devices = await self.device_repo.get_all()
        return self._enrich_zone_status(status, devices)

    async def get_all_zones(self) -> list[ZoneStatus]:
        """Get all active zones from database (no device polling)."""
        zones_db = await self.zone_repo.get_all_active_zones()
        await self.device_repo.get_all()

        result = []
        for zone_db in zones_db:
            if zone_db.id is None:
                logger.error(
                    "Zone from DB has no ID, skipping: %s", zone_db.master_device_id
                )
                continue
            members = await self.zone_repo.get_active_members(zone_db.id)

            # Enrich with device names/IPs
            member_infos = []
            for m in members:
                device = await self.device_repo.get_by_device_id(m.device_id)
                if device:
                    member_infos.append(
                        ZoneMemberInfo(
                            device_id=m.device_id,
                            ip_address=device.ip,
                            role=m.role,
                            name=device.name,
                            model=device.model,
                        )
                    )

            master = await self.device_repo.get_by_device_id(zone_db.master_device_id)
            if master:
                result.append(
                    ZoneStatus(
                        master_id=master.device_id,
                        master_ip=master.ip,
                        is_master=True,
                        members=member_infos,
                    )
                )

        logger.info(
            "get_all_zones: %d zone(s) from DB, members: %s",
            len(result),
            {z.master_id: len(z.members) for z in result},
        )
        return result

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

        # Persist to database
        try:
            zone_db = await self.zone_repo.create_zone(master.device_id)
            if zone_db.id is None:
                raise RuntimeError("Created zone has no ID")
            for slave_id in slave_ids:
                await self.zone_repo.add_member(zone_db.id, slave_id, "slave")
            logger.info("Zone created and persisted to DB: zone_id=%d", zone_db.id)
        except Exception:
            logger.exception("Failed to persist zone to DB")

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

        # Update database
        zone_db = await self.zone_repo.get_active_zone_by_master(master.device_id)
        if zone_db and zone_db.id is not None:
            for slave_id in slave_ids:
                await self.zone_repo.add_member(zone_db.id, slave_id, "slave")

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

        # Update database
        zone_db = await self.zone_repo.get_active_zone_by_master(master.device_id)
        if zone_db and zone_db.id is not None:
            for slave_id in slave_ids:
                await self.zone_repo.remove_member(zone_db.id, slave_id)

    async def _remove_slaves_parallel(
        self, client: "DeviceClient", slaves: list
    ) -> None:
        """Remove all slaves in parallel to reduce dissolution time."""
        if not slaves:
            return

        logger.info(
            "Removing %d slaves in PARALLEL before dissolving zone", len(slaves)
        )
        remove_tasks = [client.remove_zone_members([slave]) for slave in slaves]
        results = await asyncio.gather(*remove_tasks, return_exceptions=True)

        for slave, result in zip(slaves, results):
            if isinstance(result, Exception):
                logger.error("Failed to remove slave %s: %s", slave.device_id, result)
            else:
                logger.info("Slave %s removed successfully", slave.device_id)

    async def dissolve_zone(self, master_id: str) -> None:
        """Dissolve zone by removing all slaves in parallel, then master."""
        logger.info("Dissolving zone with master_id=%s", master_id)
        master = await self._get_device_or_raise(master_id)
        client = self._get_client(master.ip)

        # Get current zone to identify all slaves
        zone_status = await client.get_zone_status()

        if not zone_status or not zone_status.members:
            logger.warning(
                "No zone found for master_id=%s, nothing to dissolve", master_id
            )
            # Still update DB to mark as dissolved
            zone_db = await self.zone_repo.get_active_zone_by_master(master.device_id)
            if zone_db and zone_db.id is not None:
                await self.zone_repo.dissolve_zone(zone_db.id)
            return

        # Remove all slaves in PARALLEL (each waits with delay=3)
        slaves = [m for m in zone_status.members if m.role == "slave"]
        await self._remove_slaves_parallel(client, slaves)

        # Now dissolve the zone on master (all slaves are removed)
        try:
            await client.remove_zone()
            logger.info("Zone dissolved successfully for master_id=%s", master_id)
        except Exception:
            # Bose devices sometimes throw errors even when operation succeeds
            # Zone events will confirm if zone was actually dissolved
            logger.exception(
                "remove_zone() raised exception but zone may be dissolved (master_id=%s)",
                master_id,
            )
        finally:
            # Update database ALWAYS (even if remove_zone() threw exception)
            # Physical zone state is source of truth (WebSocket events)
            zone_db = await self.zone_repo.get_active_zone_by_master(master.device_id)
            if zone_db and zone_db.id is not None:
                await self.zone_repo.dissolve_zone(zone_db.id)
                logger.info("Zone marked as dissolved in DB (zone_id=%d)", zone_db.id)

    async def change_master(self, old_master_id: str, new_master_id: str) -> ZoneStatus:
        """Change the master of a zone. Dissolve old, recreate with new master."""
        old_master = await self._get_device_or_raise(old_master_id)
        await self._get_device_or_raise(new_master_id)  # validate exists

        # Get current zone to know members
        client = self._get_client(old_master.ip)
        current_zone = await client.get_zone_status()

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
