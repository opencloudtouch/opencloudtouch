"""Background health-check service for SoundTouch devices.

Periodically pings devices via the SoundTouch API (port 8090) to update
``last_seen`` and detect offline devices.  For devices with
``ssh_permanent=True``, also verifies the BMX URL via SSH every 30 min.
"""

import asyncio
import logging
from datetime import UTC, datetime

import httpx
from defusedxml.ElementTree import fromstring as parse_xml_string

from opencloudtouch.core.config import get_config
from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT
from opencloudtouch.setup.ssh_client import SoundTouchSSHClient, check_ssh_port

logger = logging.getLogger(__name__)

# Intervals (seconds)
PING_INTERVAL = 5 * 60  # 5 min
SSH_VERIFY_INTERVAL = 30 * 60  # 30 min
PING_TIMEOUT = 5  # HTTP timeout per device
OFFLINE_THRESHOLD = 15 * 60  # 15 min without response → offline
SSH_FAIL_THRESHOLD = 2  # consecutive failures before resetting ssh_permanent


class DeviceHealthCheck:
    """Background task that monitors device reachability and setup status."""

    def __init__(self, device_repo: DeviceRepository):
        self._device_repo = device_repo
        self._task: asyncio.Task | None = None
        self._last_ssh_verify = 0.0
        self._running = False
        self._ssh_fail_count: dict[str, int] = {}

    def start(self) -> None:
        """Start the background health-check loop."""
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="device-health-check")
        logger.info("Device health-check started")

    async def stop(self) -> None:
        """Stop the background health-check loop gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("Health-check task cancelled")
            self._task = None
            logger.info("Device health-check stopped")

    async def _run(self) -> None:
        """Main loop: ping every 5 min, SSH verify every 30 min."""
        while self._running:
            try:
                await self._ping_all_devices()

                now = asyncio.get_event_loop().time()
                if now - self._last_ssh_verify >= SSH_VERIFY_INTERVAL:
                    await self._ssh_verify_all()
                    self._last_ssh_verify = now

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Health-check cycle failed")

            await asyncio.sleep(PING_INTERVAL)

    async def _ping_all_devices(self) -> None:
        """Ping all devices via SoundTouch HTTP API (port 8090)."""
        devices = await self._device_repo.get_all()
        if not devices:
            return

        now = datetime.now(UTC)

        async with httpx.AsyncClient(timeout=PING_TIMEOUT) as client:
            for device in devices:
                if not device.ip:
                    continue
                reachable, device_name = await self._ping_device(client, device.ip)
                if reachable:
                    await self._handle_reachable(device, device_name, now)
                else:
                    self._handle_unreachable(device, now)

        logger.debug("Health-check ping completed for %d devices", len(devices))

    async def _handle_reachable(
        self, device, device_name: str | None, now: datetime
    ) -> None:
        """Update a reachable device: refresh last_seen and name if changed."""
        device.last_seen = now
        if device_name and device_name != device.name:
            logger.info(
                "Device %s name changed: '%s' -> '%s'",
                device.device_id,
                device.name,
                device_name,
            )
            device.name = device_name
        await self._device_repo.upsert(device)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into human-readable duration string."""
        total_minutes = int(seconds) // 60
        years, remainder = divmod(total_minutes, 525960)  # 365.25 days
        days, remainder = divmod(remainder, 1440)
        hours, minutes = divmod(remainder, 60)
        parts = []
        if years == 1:
            parts.append("1 year")
        elif years > 1:
            parts.append(f"{years} years")
        if days == 1:
            parts.append("1 day")
        elif days > 0:
            parts.append(f"{days} days")
        if hours == 1:
            parts.append("1 hour")
        elif hours > 0:
            parts.append(f"{hours} hours")
        if minutes == 1:
            parts.append("1 minute")
        else:
            parts.append(f"{minutes} minutes")
        return ", ".join(parts)

    @staticmethod
    def _handle_unreachable(device, now: datetime) -> None:
        """Log a warning if the device has been offline beyond the threshold."""
        if not device.last_seen:
            return
        seconds_since = (now - device.last_seen).total_seconds()
        if seconds_since > OFFLINE_THRESHOLD:
            logger.warning(
                "Device %s (%s) offline for %s",
                device.name,
                device.ip,
                DeviceHealthCheck._format_duration(seconds_since),
            )

    @staticmethod
    async def _ping_device(
        client: httpx.AsyncClient, ip: str
    ) -> tuple[bool, str | None]:
        """Ping a single device via GET /info on the WebServer port.

        Returns:
            Tuple of (reachable, device_name). device_name is None if
            the response could not be parsed.
        """
        try:
            resp = await client.get(
                f"http://{ip}:{SOUNDTOUCH_HTTP_PORT}/info"  # NOSONAR — Bose devices only support HTTP
            )
            if resp.status_code != 200:
                return False, None
            # Extract device name from XML response
            device_name: str | None = None
            try:
                root = parse_xml_string(resp.content)
                name_el = root.find("name")
                if name_el is not None and name_el.text:
                    device_name = name_el.text.strip()
            except Exception:
                logger.debug("Failed to parse device name from /info response (%s)", ip)
            return True, device_name
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError):
            return False, None
        except Exception:
            return False, None

    async def _ssh_verify_all(self) -> None:
        """Verify BMX URL via SSH for devices with ssh_permanent=True."""
        devices = await self._device_repo.get_all()
        config = get_config()
        our_server = (
            config.station_descriptor_base_url
            or f"http://{config.host}:{config.port}"  # NOSONAR — LAN only
        )

        for device in devices:
            if not device.ssh_permanent or not device.ip:
                continue

            try:
                await self._ssh_verify_device(device, our_server)
            except Exception:
                logger.debug("SSH verify failed for %s (%s)", device.name, device.ip)

    async def _ssh_verify_device(self, device, our_server: str) -> None:
        """Verify a single device via SSH: check BMX URL and update status."""
        if not await check_ssh_port(device.ip, timeout=3.0):
            count = self._ssh_fail_count.get(device.device_id, 0) + 1
            self._ssh_fail_count[device.device_id] = count
            if count >= SSH_FAIL_THRESHOLD:
                logger.warning(
                    "SSH unreachable for %s (%d cycles) — disabling ssh_permanent",
                    device.name,
                    count,
                )
                await self._device_repo.update_setup_status(
                    device_id=device.device_id,
                    setup_status=device.setup_status,
                    ssh_permanent=False,
                )
            else:
                logger.debug("SSH not reachable for %s", device.name)
            return

        # SSH reachable — reset failure counter
        self._ssh_fail_count[device.device_id] = 0

        client = SoundTouchSSHClient(device.ip)
        conn = await client.connect(timeout=5.0)
        if not conn.success:
            return

        try:
            # Check BMX URL (Strategy A: direct URL change)
            result = await client.execute(
                "cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml "
                "| grep -i bmxRegistryUrl"
            )
            bmx_output = result.output or ""

            # Check /etc/hosts (Strategy B: hosts redirect via reverse proxy)
            hosts_result = await client.execute(
                "grep -c 'OCT-START' /etc/hosts 2>/dev/null || echo '0'"
            )
            has_hosts_redirect = hosts_result.output.strip() != "0"

            if our_server in bmx_output or has_hosts_redirect:
                new_status = "configured"
            elif "bose.com" in bmx_output.lower():
                new_status = "unconfigured"
            elif "bmxRegistryUrl" in bmx_output:
                new_status = "outdated"
            else:
                return  # Can't determine — keep current status

            if new_status != device.setup_status:
                logger.info(
                    "Device %s status changed: %s → %s",
                    device.name,
                    device.setup_status,
                    new_status,
                )
                await self._device_repo.update_setup_status(
                    device_id=device.device_id,
                    setup_status=new_status,
                )
        finally:
            await client.close()
