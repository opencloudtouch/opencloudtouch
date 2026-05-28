"""One-time startup check: verify setup_status for 'unknown' devices via HTTP /info."""

import logging
from datetime import UTC, datetime

import httpx
from defusedxml.ElementTree import fromstring as parse_xml

from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT

logger = logging.getLogger(__name__)

CHECK_TIMEOUT = 5  # HTTP timeout per device


class StartupCheck:
    """One-time startup check: verify setup_status for 'unknown' devices via HTTP /info."""

    def __init__(self, device_repo: DeviceRepository):
        self._device_repo = device_repo

    async def run(self) -> None:
        """Check all devices with setup_status='unknown' and update based on /info margeURL."""
        devices = await self._device_repo.get_all()
        unknown_devices = [d for d in devices if d.setup_status == "unknown"]

        if not unknown_devices:
            logger.debug("Startup check: no devices with status 'unknown'")
            return

        logger.info(
            "Startup check: verifying %d device(s) with status 'unknown'",
            len(unknown_devices),
        )

        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT) as client:
            for device in unknown_devices:
                if not device.ip:
                    continue
                await self._check_device(client, device)

    async def _check_device(self, client: httpx.AsyncClient, device) -> None:
        """Query /info for a single device and update setup_status based on margeURL."""
        url = f"http://{device.ip}:{SOUNDTOUCH_HTTP_PORT}/info"  # NOSONAR — Bose devices only support HTTP
        logger.debug(
            "Startup check: probing device %s (%s) at %s",
            device.name,
            device.device_id,
            url,
        )
        try:
            resp = await client.get(url)
            logger.debug(
                "Startup check: device %s (%s) responded HTTP %d (%d bytes)",
                device.name,
                device.device_id,
                resp.status_code,
                len(resp.text),
            )
            if resp.status_code != 200:
                logger.warning(
                    "Startup check: device %s (%s) returned HTTP %d",
                    device.name,
                    device.device_id,
                    resp.status_code,
                )
                return

            marge_url = self._extract_marge_url(resp.text)
            logger.debug(
                "Startup check: device %s (%s) margeURL=%s",
                device.name,
                device.device_id,
                marge_url,
            )
            if marge_url is None:
                logger.debug(
                    "Startup check: device %s (%s) no margeURL in response, skipping",
                    device.name,
                    device.device_id,
                )
                return

            new_status = self._determine_status(marge_url)
            logger.debug(
                "Startup check: device %s (%s) determined status=%s (current=%s)",
                device.name,
                device.device_id,
                new_status,
                device.setup_status,
            )
            if new_status is None or new_status == device.setup_status:
                return

            completed_at = datetime.now(UTC) if new_status == "configured" else None
            await self._device_repo.update_setup_status(
                device_id=device.device_id,
                setup_status=new_status,
                setup_completed_at=completed_at,
            )
            logger.info(
                "Startup check: device %s (%s) status: %s → %s",
                device.name,
                device.device_id,
                device.setup_status,
                new_status,
            )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError):
            logger.debug(
                "Startup check: device %s (%s) unreachable, keeping status 'unknown'",
                device.name,
                device.device_id,
            )
        except Exception:
            logger.exception(
                "Startup check: unexpected error for device %s (%s)",
                device.name,
                device.device_id,
            )

    @staticmethod
    def _extract_marge_url(xml_text: str) -> str | None:
        """Extract margeURL from /info XML response."""
        try:
            root = parse_xml(xml_text)
            elem = root.find("margeURL")
            if elem is not None and elem.text:
                return elem.text.strip()
        except Exception:
            logger.exception("Failed to parse /info XML")
        return None

    @staticmethod
    def _determine_status(marge_url: str) -> str | None:
        """Determine setup_status from margeURL value."""
        if "content.api.bose.io" in marge_url:
            return "configured"
        if "streaming.bose.com" in marge_url:
            return "unconfigured"
        return None
