"""
SSDP Discovery for Bose SoundTouch devices.

Uses SSDP (Simple Service Discovery Protocol) over UPnP instead of mDNS/Zeroconf
to avoid port conflicts with system services like avahi-daemon.

Bose SoundTouch devices announce themselves via SSDP on port 1900.
"""

import asyncio
import logging
import socket
from typing import Dict, Optional
from xml.etree.ElementTree import Element

import httpx
from defusedxml.ElementTree import fromstring as parse_xml_string

logger = logging.getLogger(__name__)


class SSDPDiscovery:
    """
    SSDP-based discovery for Bose SoundTouch devices.

    Uses M-SEARCH multicast to discover UPnP devices, then filters
    for Bose SoundTouch devices by parsing their description XML.
    """

    SSDP_MULTICAST_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    SEARCH_TARGET = "ssdp:all"  # Broad search, filter by manufacturer later
    MX_DELAY = 3  # Max delay for device responses (seconds)

    def __init__(self, timeout: int = 10):
        """
        Initialize SSDP discovery.

        Args:
            timeout: Discovery timeout in seconds
        """
        self.timeout = timeout

    async def discover(self) -> Dict[str, Dict[str, str]]:
        """
        Discover Bose SoundTouch devices on the network via SSDP.

        Returns:
            Dict mapping device MAC addresses to device info:
            {
                "MAC_ADDRESS": {
                    "ip": "192.168.1.100",
                    "mac": "MAC_ADDRESS",
                    "name": "Living Room",
                    "model": "SoundTouch 20"
                }
            }
        """
        logger.info(f"Starting SSDP discovery (timeout: {self.timeout}s)")

        try:
            # Run SSDP M-SEARCH in executor (blocking I/O)
            loop = asyncio.get_event_loop()
            locations = await loop.run_in_executor(None, self._ssdp_msearch)

            # Fetch and parse device descriptions
            devices = await self._fetch_device_descriptions(locations)

            logger.info(f"SSDP discovery found {len(devices)} Bose device(s)")
            return devices

        except Exception as e:
            logger.error(f"SSDP discovery failed: {e}", exc_info=True)
            return {}

    def _ssdp_msearch(self) -> list[str]:
        """
        Send SSDP M-SEARCH multicast and collect device location URLs.

        Returns:
            List of device description URLs (e.g., http://192.168.1.100:8090/device.xml)
        """
        # Create UDP socket for multicast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Join multicast group (CRITICAL for receiving responses!)
        # Binding to 0.0.0.0 required for SSDP multicast membership
        mreq = socket.inet_aton(self.SSDP_MULTICAST_ADDR) + socket.inet_aton(
            "0.0.0.0"
        )  # nosec B104
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Bind to SSDP port to receive responses
        sock.bind(("", self.SSDP_PORT))

        sock.settimeout(self.timeout)

        # M-SEARCH message
        msg = (
            f"M-SEARCH * HTTP/1.1\r\n"
            f"HOST: {self.SSDP_MULTICAST_ADDR}:{self.SSDP_PORT}\r\n"
            f'MAN: "ssdp:discover"\r\n'
            f"MX: {self.MX_DELAY}\r\n"
            f"ST: {self.SEARCH_TARGET}\r\n"
            f"\r\n"
        ).encode("utf-8")

        locations = set()

        try:
            # Send M-SEARCH
            try:
                sock.sendto(msg, (self.SSDP_MULTICAST_ADDR, self.SSDP_PORT))
                logger.debug("Sent SSDP M-SEARCH multicast")
            except OSError as e:
                logger.error(f"Failed to send SSDP M-SEARCH: {e}")
                return []

            # Collect responses
            while True:
                try:
                    data, addr = sock.recvfrom(8192)
                    response = data.decode("utf-8", errors="ignore")

                    # Extract LOCATION header
                    location = self._parse_location(response)
                    if location:
                        locations.add(location)
                        logger.debug(f"Found SSDP device at {location}")

                except socket.timeout:
                    break
                except Exception as e:
                    logger.debug(f"Error receiving SSDP response: {e}")
                    break

        finally:
            sock.close()

        logger.info(f"SSDP M-SEARCH found {len(locations)} device(s)")
        return list(locations)

    def _parse_location(self, response: str) -> Optional[str]:
        """
        Parse LOCATION header from SSDP response.

        Args:
            response: Raw SSDP HTTP response

        Returns:
            Location URL or None
        """
        for line in response.split("\r\n"):
            if line.lower().startswith("location:"):
                return line.split(":", 1)[1].strip()
        return None

    async def _fetch_device_descriptions(
        self, locations: list[str]
    ) -> Dict[str, Dict[str, str]]:
        """
        Fetch and parse device description XMLs, filter for Bose devices.

        Args:
            locations: List of device description URLs

        Returns:
            Dict of Bose devices by MAC address
        """
        devices = {}

        # Use higher connection limit to parallelize more aggressively
        # Reduce timeout from 5s to 2s (non-Bose devices don't need to be slow)
        async with httpx.AsyncClient(
            timeout=2.0,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        ) as client:
            tasks = [self._fetch_and_parse_device(client, loc) for loc in locations]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, dict) and result:
                    mac = result.get("mac")
                    if mac:
                        devices[mac] = result

        return devices

    async def _fetch_and_parse_device(
        self, client: httpx.AsyncClient, location: str
    ) -> Optional[Dict[str, str]]:
        """
        Fetch device description XML and parse Bose SoundTouch info.

        Args:
            client: HTTP client
            location: Device description URL

        Returns:
            Device info dict or None if not a Bose device
        """
        try:
            response = await client.get(location)
            response.raise_for_status()

            # Parse XML securely using defusedxml
            root = parse_xml_string(response.text)

            # Check if it's a Bose device
            manufacturer = self._find_xml_text(root, ".//manufacturer")
            if not manufacturer or "bose" not in manufacturer.lower():
                return None

            # Extract device info
            friendly_name = (
                self._find_xml_text(root, ".//friendlyName") or "Unknown Bose Device"
            )
            model_name = self._find_xml_text(root, ".//modelName") or "Unknown Model"
            serial = self._find_xml_text(root, ".//serialNumber") or ""

            # Extract IP from location URL
            ip = self._extract_ip_from_url(location)
            if not ip:
                return None

            # Use serial as MAC (Bose uses serial/MAC interchangeably)
            # Format: AA:BB:CC:DD:EE:FF or AABBCCDDEEFF
            mac = serial.upper()

            logger.info(f"Found Bose device: {friendly_name} ({model_name}) at {ip}")

            return {
                "ip": ip,
                "mac": mac,
                "name": friendly_name,
                "model": model_name,
            }

        except Exception as e:
            logger.debug(f"Failed to parse device at {location}: {e}")
            return None

    def _find_xml_text(self, root: Element, path: str) -> Optional[str]:
        """
        Find XML element text with proper namespace handling.

        Extracts namespace from root element and uses it for XPath queries.
        Falls back to namespace-agnostic search if no namespace is found.

        Args:
            root: XML root element
            path: XPath to element (e.g., ".//manufacturer")

        Returns:
            Element text or None
        """
        # Extract namespace from root tag (e.g., {urn:schemas-upnp-org:device-1-0})
        namespace = None
        if root.tag.startswith("{"):
            namespace = root.tag[1 : root.tag.index("}")]

        # Build proper XPath with namespace
        if namespace and path.startswith(".//"):
            tag_name = path[3:]  # Remove ".//"
            # Use namespace map for proper XPath query
            namespaces = {"ns": namespace}
            elem = root.find(f".//ns:{tag_name}", namespaces)
            if elem is not None and elem.text:
                return elem.text.strip()

        # Fallback: Try without namespace (for non-namespaced XML)
        elem = root.find(path)
        if elem is not None and elem.text:
            return elem.text.strip()

        return None

    def _extract_ip_from_url(self, url: str) -> Optional[str]:
        """
        Extract IP address from URL.

        Args:
            url: URL like http://192.168.1.100:8090/device.xml

        Returns:
            IP address or None
        """
        try:
            # Parse URL: http://IP:PORT/path
            parts = url.split("://")[1].split(":")[0]
            return parts
        except Exception:
            return None
