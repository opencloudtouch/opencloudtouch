"""Discovery of DLNA/UPnP media servers."""

import asyncio
import logging
import ipaddress
from urllib.parse import urljoin, urlsplit

import httpx
from defusedxml.ElementTree import fromstring as parse_xml_string

from opencloudtouch.dlna.models import DlnaServer
from opencloudtouch.devices.discovery.ssdp import SSDPDiscovery

logger = logging.getLogger(__name__)


class DlnaDiscovery:
    """Discover UPnP MediaServer devices and their ContentDirectory service."""

    SEARCH_TARGET = "urn:schemas-upnp-org:device:MediaServer:1"

    def __init__(self, timeout: int = 5):
        self.ssdp = SSDPDiscovery(timeout=timeout, search_target=self.SEARCH_TARGET)

    async def discover(self) -> list[DlnaServer]:
        """Discover UPnP MediaServers with the shared SSDP implementation."""
        try:
            locations = await asyncio.to_thread(self.ssdp._ssdp_msearch)
            return await self._fetch_server_descriptions(locations)
        except Exception:
            logger.exception("DLNA discovery failed")
            return []

    @staticmethod
    def _valid_http_url(url: str, expected_host: str | None = None) -> bool:
        """Perform basic URL sanity checks while allowing LAN media servers.

        This is not a complete SSRF defense: DNS hostnames are not resolved
        or pinned, and DNS rebinding is outside the scope of this check.
        """
        try:
            parsed = urlsplit(url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.hostname.lower() == "localhost"
                or parsed.hostname.lower().endswith(".localhost")
                or parsed.username is not None
                or parsed.password is not None
                or (
                    expected_host is not None
                    and parsed.hostname.lower() != expected_host.lower()
                )
            ):
                return False
            _ = parsed.port  # Raises ValueError for invalid ports.
            if parsed.port == 0:
                return False
            try:
                address = ipaddress.ip_address(parsed.hostname)
            except ValueError:
                return True
            return not (
                address.is_loopback or address.is_multicast or address.is_unspecified
            )
        except ValueError:
            return False

    async def _fetch_server_descriptions(
        self,
        locations: list[str],
    ) -> list[DlnaServer]:
        """Fetch UPnP descriptions and return valid MediaServer devices."""
        if not locations:
            return []

        async with httpx.AsyncClient(
            timeout=3.0, trust_env=False, follow_redirects=False
        ) as client:
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
        if not self._valid_http_url(location):
            logger.debug("Rejected DLNA LOCATION: %s", location)
            return None

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

            resolved_control_url = urljoin(location, control_url)
            if not self._valid_http_url(
                resolved_control_url, expected_host=urlsplit(location).hostname
            ):
                logger.debug("Rejected DLNA control URL: %s", resolved_control_url)
                return None

            server_id = udn.removeprefix("uuid:")

            return DlnaServer(
                id=server_id,
                name=friendly_name,
                location=location,
                control_url=resolved_control_url,
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
