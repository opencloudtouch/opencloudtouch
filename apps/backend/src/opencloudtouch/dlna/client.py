"""DLNA ContentDirectory client."""

import logging
from xml.etree.ElementTree import Element

import httpx
from defusedxml.ElementTree import fromstring as parse_xml_string

from opencloudtouch.dlna.models import DlnaItem, DlnaServer

logger = logging.getLogger(__name__)


class DlnaBrowseError(Exception):
    """Raised when a DLNA ContentDirectory browse operation fails."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code


class DlnaClient:
    """Browse a DLNA MediaServer ContentDirectory."""

    CONTENT_DIRECTORY_SERVICE = "urn:schemas-upnp-org:service:ContentDirectory:1"

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    async def browse(
        self,
        server: DlnaServer,
        object_id: str = "0",
    ) -> list[DlnaItem]:
        """Browse direct children of a DLNA ContentDirectory object."""
        body = self._build_browse_request(object_id)

        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"{self.CONTENT_DIRECTORY_SERVICE}#Browse"',
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    server.control_url,
                    content=body,
                    headers=headers,
                )
        except httpx.RequestError as exc:
            raise DlnaBrowseError(
                f"Could not contact DLNA server: {server.name}"
            ) from exc

        if response.is_error:
            raise self._parse_error_response(response)

        try:
            return self._parse_browse_response(response.text)
        except Exception as exc:
            raise DlnaBrowseError(
                f"Invalid browse response from DLNA server: {server.name}"
            ) from exc

    @classmethod
    def _build_browse_request(cls, object_id: str) -> str:
        """Build a SOAP BrowseDirectChildren request."""
        return f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope
    xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
    s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Browse xmlns:u="{cls.CONTENT_DIRECTORY_SERVICE}">
      <ObjectID>{cls._escape_xml(object_id)}</ObjectID>
      <BrowseFlag>BrowseDirectChildren</BrowseFlag>
      <Filter>*</Filter>
      <StartingIndex>0</StartingIndex>
      <RequestedCount>0</RequestedCount>
      <SortCriteria></SortCriteria>
    </u:Browse>
  </s:Body>
</s:Envelope>"""

    @classmethod
    def _parse_browse_response(cls, xml: str) -> list[DlnaItem]:
        """Parse the SOAP response and contained DIDL-Lite document."""
        root = parse_xml_string(xml)

        result = cls._find_text(root, "Result")
        if not result:
            return []

        didl_root = parse_xml_string(result)
        items: list[DlnaItem] = []

        for element in didl_root:
            local_name = cls._local_name(element.tag)

            if local_name not in {"container", "item"}:
                continue

            item_id = element.attrib.get("id")
            parent_id = element.attrib.get("parentID")

            if not item_id or parent_id is None:
                continue

            title = cls._find_text(element, "title")
            media_class = cls._find_text(element, "class")

            artist = cls._find_text(element, "artist")
            album = cls._find_text(element, "album")
            genre = cls._find_text(element, "genre")
            creator = cls._find_text(element, "creator")
            album_art_url = cls._find_text(element, "albumArtURI")

            resource = cls._find_element(element, "res")

            resource_url = None
            duration = None
            size = None
            bitrate = None
            sample_frequency = None
            audio_channels = None
            protocol_info = None

            if resource is not None:
                if resource.text:
                    resource_url = resource.text.strip()

                duration = resource.attrib.get("duration")
                protocol_info = resource.attrib.get("protocolInfo")

                size = cls._parse_int(resource.attrib.get("size"))
                bitrate = cls._parse_int(resource.attrib.get("bitrate"))
                sample_frequency = cls._parse_int(
                    resource.attrib.get("sampleFrequency")
                )
                audio_channels = cls._parse_int(resource.attrib.get("nrAudioChannels"))

            items.append(
                DlnaItem(
                    id=item_id,
                    parent_id=parent_id,
                    title=title or item_id,
                    is_container=local_name == "container",
                    resource_url=resource_url,
                    media_class=media_class,
                    artist=artist,
                    album=album,
                    genre=genre,
                    creator=creator,
                    album_art_url=album_art_url,
                    duration=duration,
                    size=size,
                    bitrate=bitrate,
                    sample_frequency=sample_frequency,
                    audio_channels=audio_channels,
                    protocol_info=protocol_info,
                )
            )

        return items

    @classmethod
    def _parse_error_response(
        cls,
        response: httpx.Response,
    ) -> DlnaBrowseError:
        """Convert a UPnP SOAP error response into a DLNA exception."""
        error_code = None
        error_description = None

        try:
            root = parse_xml_string(response.text)
            error_code = cls._find_text(root, "errorCode")
            error_description = cls._find_text(root, "errorDescription")
        except Exception:
            logger.debug("Could not parse DLNA SOAP fault response")

        if error_description:
            message = error_description
        elif error_code:
            message = f"DLNA browse failed with UPnP error {error_code}"
        else:
            message = f"DLNA browse failed with HTTP {response.status_code}"

        return DlnaBrowseError(
            message,
            error_code=error_code,
        )

    @staticmethod
    def _escape_xml(value: str) -> str:
        """Escape text inserted into a SOAP XML element."""
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    @staticmethod
    def _local_name(tag: str) -> str:
        """Return an XML tag name without its namespace."""
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _find_text(cls, root: Element, name: str) -> str | None:
        """Find the first XML element by namespace-independent local name."""
        for element in root.iter():
            if cls._local_name(element.tag) == name and element.text:
                return element.text.strip()

        return None

    @classmethod
    def _find_element(cls, root: Element, name: str) -> Element | None:
        """Find the first XML element by namespace-independent local name."""
        for element in root.iter():
            if cls._local_name(element.tag) == name:
                return element

        return None

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        """Convert an optional DLNA numeric attribute to int."""
        if value is None:
            return None

        try:
            return int(value)
        except ValueError:
            return None
