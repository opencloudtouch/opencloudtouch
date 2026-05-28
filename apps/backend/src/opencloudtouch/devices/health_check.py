"""Background health-check service for SoundTouch devices.

Periodically pings devices via the SoundTouch API (port 8090) to update
``last_seen`` and detect offline devices.  For devices with
``ssh_permanent=True``, also verifies the BMX URL via SSH every 30 min.
"""

import asyncio
import logging
from datetime import UTC, datetime

import httpx

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
        """Ping all devices via SoundTouch HTTP API (port 8091)."""
        devices = await self._device_repo.get_all()
        if not devices:
            return

        now = datetime.now(UTC)

        async with httpx.AsyncClient(timeout=PING_TIMEOUT) as client:
            for device in devices:
                if not device.ip:
                    continue
                reachable = await self._ping_device(client, device.ip)
                if reachable:
                    device.last_seen = now
                    await self._device_repo.upsert(device)
                else:
                    # Check if device should be marked offline
                    if device.last_seen:
                        seconds_since = (now - device.last_seen).total_seconds()
                        if seconds_since > OFFLINE_THRESHOLD:
                            logger.warning(
                                "Device %s (%s) offline for %.0fs",
                                device.name,
                                device.ip,
                                seconds_since,
                            )

        logger.debug("Health-check ping completed for %d devices", len(devices))

    @staticmethod
    async def _ping_device(client: httpx.AsyncClient, ip: str) -> bool:
        """Ping a single device via GET /info on the WebServer port."""
        try:
            resp = await client.get(
                f"http://{ip}:{SOUNDTOUCH_HTTP_PORT}/info"  # NOSONAR — Bose devices only support HTTP
            )
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError):
            return False
        except Exception:
            return False

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
