"""Discovery of DLNA/UPnP media servers."""

import asyncio
import logging
import socket
import time
from urllib.parse import urljoin

import httpx
from defusedxml.ElementTree import fromstring as parse_xml_string

from opencloudtouch.dlna.models import DlnaServer

logger = logging.getLogger(__name__)


class DlnaDiscovery:
    """Discover UPnP MediaServer devices and their ContentDirectory service."""

    SSDP_MULTICAST_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    SEARCH_TARGET = "urn:schemas-upnp-org:device:MediaServer:1"
    MX_DELAY = 2

    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    async def discover(self) -> list[DlnaServer]:
        """Discover available DLNA media servers."""
        try:
            locations = await asyncio.to_thread(self._ssdp_msearch)
            return await self._fetch_server_descriptions(locations)
        except Exception:
            logger.exception("DLNA discovery failed")
            return []

    def _ssdp_msearch(self) -> list[str]:
        """Send an SSDP M-SEARCH and return unique LOCATION URLs."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        deadline = time.monotonic() + self.timeout

        message = (
            "M-SEARCH * HTTP/1.1\r\n"
            f"HOST: {self.SSDP_MULTICAST_ADDR}:{self.SSDP_PORT}\r\n"
            'MAN: "ssdp:discover"\r\n'
            f"MX: {self.MX_DELAY}\r\n"
            f"ST: {self.SEARCH_TARGET}\r\n"
            "\r\n"
        ).encode("utf-8")

        locations: set[str] = set()

        try:
            sock.sendto(
                message,
                (self.SSDP_MULTICAST_ADDR, self.SSDP_PORT),
            )

            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                sock.settimeout(min(remaining, 0.1))

                try:
                    data, _ = sock.recvfrom(8192)
                except socket.timeout:
                    continue

                response = data.decode("utf-8", errors="ignore")
                location = self._parse_location(response)

                if location:
                    locations.add(location)
        except OSError:
            logger.exception("DLNA SSDP discovery failed")
        finally:
            sock.close()

        return list(locations)

    @staticmethod
    def _parse_location(response: str) -> str | None:
        """Extract the LOCATION header from an SSDP response."""
        for line in response.split("\r\n"):
            if line.lower().startswith("location:"):
                return line.split(":", 1)[1].strip()

        return None

    async def _fetch_server_descriptions(
        self,
        locations: list[str],
    ) -> list[DlnaServer]:
        """Fetch UPnP descriptions and return valid MediaServer devices."""
        if not locations:
            return []

        async with httpx.AsyncClient(timeout=3.0) as client:
            results = await asyncio.gather(
                *(
                    self._fetch_and_parse_server(client, location)
                    for location in locations
                ),
                return_exceptions=True,
            )

        servers = [result for result in results if isinstance(result, DlnaServer)]

        logger.info("DLNA discovery found %d media server(s)", len(servers))
        return servers

    async def _fetch_and_parse_server(
        self,
        client: httpx.AsyncClient,
        location: str,
    ) -> DlnaServer | None:
        """Parse a UPnP description and locate its ContentDirectory service."""
        try:
            response = await client.get(location)
            response.raise_for_status()

            root = parse_xml_string(response.text)

            device_type = self._find_text(root, "deviceType")
            if not device_type or "MediaServer" not in device_type:
                return None

            friendly_name = self._find_text(root, "friendlyName")
            udn = self._find_text(root, "UDN")

            if not friendly_name or not udn:
                return None

            control_url = self._find_content_directory_control_url(root)
            if not control_url:
                return None

            server_id = udn.removeprefix("uuid:")

            return DlnaServer(
                id=server_id,
                name=friendly_name,
                location=location,
                control_url=urljoin(location, control_url),
            )
        except Exception as exc:
            logger.debug(
                "Failed to parse DLNA server description at %s: %s",
                location,
                exc,
            )
            return None

    @staticmethod
    def _local_name(tag: str) -> str:
        """Return an XML tag name without its namespace."""
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _find_text(cls, root, name: str) -> str | None:
        """Find the first XML element by namespace-independent local name."""
        for element in root.iter():
            if cls._local_name(element.tag) == name and element.text:
                return element.text.strip()

        return None

    @classmethod
    def _find_content_directory_control_url(cls, root) -> str | None:
        """Find the ContentDirectory service control URL."""
        for service in root.iter():
            if cls._local_name(service.tag) != "service":
                continue

            service_type = None
            control_url = None

            for child in service:
                name = cls._local_name(child.tag)

                if name == "serviceType" and child.text:
                    service_type = child.text.strip()
                elif name == "controlURL" and child.text:
                    control_url = child.text.strip()

            if (
                service_type
                and "urn:schemas-upnp-org:service:ContentDirectory:" in service_type
            ):
                return control_url

        return None
