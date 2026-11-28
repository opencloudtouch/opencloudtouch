"""DLNA ContentDirectory client."""

import logging
from xml.etree.ElementTree import Element

import httpx
from defusedxml.ElementTree import fromstring as parse_xml_string

from opencloudtouch.dlna import mock
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer

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


class DlnaTimeoutError(DlnaBrowseError):
    """Raised when the media server does not answer in time."""


class DlnaSearchUnsupportedError(DlnaBrowseError):
    """Raised when a media server cannot search by title."""


class DlnaClient:
    """Browse a DLNA MediaServer ContentDirectory."""

    CONTENT_DIRECTORY_SERVICE = "urn:schemas-upnp-org:service:ContentDirectory:1"

    def __init__(self, timeout: float = 5.0, search_timeout: float = 15.0):
        self.timeout = timeout
        # Measured server-side Search pages take up to ~7 s, far above browse times.
        self.search_timeout = search_timeout

    async def browse(
        self,
        server: DlnaServer,
        object_id: str = "0",
        starting_index: int = 0,
        requested_count: int = 50,
    ) -> BrowsePage:
        """Browse one page of direct children of a ContentDirectory object."""
        return await self._browse(
            server, object_id, "BrowseDirectChildren", starting_index, requested_count
        )

    async def get_object(self, server: DlnaServer, object_id: str) -> DlnaItem:
        """Read the metadata of one object (BrowseMetadata)."""
        page = await self._browse(server, object_id, "BrowseMetadata", 0, 1)
        if not page.items:
            raise DlnaBrowseError("No Such Object", error_code="701")
        return page.items[0]

    async def _browse(
        self,
        server: DlnaServer,
        object_id: str,
        browse_flag: str,
        starting_index: int,
        requested_count: int,
    ) -> BrowsePage:
        if server.control_url.startswith("mock://"):
            try:
                if browse_flag == "BrowseMetadata":
                    return BrowsePage([mock.mock_object(object_id)], 1, 1)
                return mock.mock_browse(object_id, starting_index, requested_count)
            except KeyError:
                raise DlnaBrowseError("No Such Object", error_code="701") from None

        body = self._build_browse_request(
            object_id, starting_index, requested_count, browse_flag
        )
        text = await self._soap(server, "Browse", body, self.timeout)
        return self._parse_response(server, text, "BrowseResponse")

    async def get_search_capabilities(self, server: DlnaServer) -> list[str]:
        """Properties the server can search by; empty if it lists none."""
        if server.control_url.startswith("mock://"):
            return mock.MOCK_SEARCH_CAPABILITIES
        body = self._envelope(
            f'<u:GetSearchCapabilities xmlns:u="{self.CONTENT_DIRECTORY_SERVICE}"/>'
        )
        text = await self._soap(server, "GetSearchCapabilities", body, self.timeout)
        try:
            root = parse_xml_string(text)
        except Exception as exc:
            raise DlnaBrowseError(
                f"Invalid search capabilities from DLNA server: {server.name}"
            ) from exc
        self._raise_fault(root)
        caps = self._find_text(root, "SearchCaps") or ""
        return [c.strip() for c in caps.split(",") if c.strip()]

    async def search(
        self,
        server: DlnaServer,
        container_id: str,
        criteria: str,
        starting_index: int = 0,
        requested_count: int = 50,
    ) -> BrowsePage:
        """Run one page of a ContentDirectory Search below a container."""
        if server.control_url.startswith("mock://"):
            try:
                return mock.mock_search(
                    container_id, criteria, starting_index, requested_count
                )
            except KeyError:
                raise DlnaBrowseError("No Such Container", error_code="710") from None
        body = self._envelope(f"""<u:Search xmlns:u="{self.CONTENT_DIRECTORY_SERVICE}">
      <ContainerID>{self._escape_xml(container_id)}</ContainerID>
      <SearchCriteria>{self._escape_xml(criteria)}</SearchCriteria>
      <Filter>*</Filter>
      <StartingIndex>{starting_index}</StartingIndex>
      <RequestedCount>{requested_count}</RequestedCount>
      <SortCriteria></SortCriteria>
    </u:Search>""")
        text = await self._soap(server, "Search", body, self.search_timeout)
        return self._parse_response(server, text, "SearchResponse")

    async def _soap(
        self, server: DlnaServer, action: str, body: str, timeout: float
    ) -> str:
        """POST one ContentDirectory action; return the response text."""
        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"{self.CONTENT_DIRECTORY_SERVICE}#{action}"',
        }

        try:
            async with httpx.AsyncClient(
                timeout=timeout, trust_env=False, follow_redirects=False
            ) as client:
                response = await client.post(
                    server.control_url,
                    content=body,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise DlnaTimeoutError(f"DLNA server timed out: {server.name}") from exc
        except httpx.RequestError as exc:
            raise DlnaBrowseError(
                f"Could not contact DLNA server: {server.name}"
            ) from exc

        if response.is_error:
            raise self._parse_error_response(response)
        return response.text

    @classmethod
    def _parse_response(
        cls, server: DlnaServer, text: str, response_name: str
    ) -> BrowsePage:
        try:
            return cls._parse_browse_response(text, response_name)
        except DlnaBrowseError:
            raise
        except Exception as exc:
            raise DlnaBrowseError(
                f"Invalid browse response from DLNA server: {server.name}"
            ) from exc

    @staticmethod
    def _envelope(body: str) -> str:
        return f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope
    xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
    s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    {body}
  </s:Body>
</s:Envelope>"""

    @classmethod
    def _build_browse_request(
        cls,
        object_id: str,
        starting_index: int = 0,
        requested_count: int = 0,
        browse_flag: str = "BrowseDirectChildren",
    ) -> str:
        """Build a SOAP Browse request."""
        return f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope
    xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
    s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Browse xmlns:u="{cls.CONTENT_DIRECTORY_SERVICE}">
      <ObjectID>{cls._escape_xml(object_id)}</ObjectID>
      <BrowseFlag>{browse_flag}</BrowseFlag>
      <Filter>*</Filter>
      <StartingIndex>{starting_index}</StartingIndex>
      <RequestedCount>{requested_count}</RequestedCount>
      <SortCriteria></SortCriteria>
    </u:Browse>
  </s:Body>
</s:Envelope>"""

    @classmethod
    def _raise_fault(cls, root: Element) -> None:
        """Raise a DlnaBrowseError if the SOAP body is a fault."""
        if cls._find_element(root, "Fault") is None:
            return
        error_code = cls._find_text(root, "errorCode")
        description = cls._find_text(root, "errorDescription") or cls._find_text(
            root, "faultstring"
        )
        message = description or (
            f"DLNA SOAP fault ({error_code})" if error_code else "DLNA SOAP fault"
        )
        raise DlnaBrowseError(message, error_code=error_code)

    @classmethod
    def _parse_browse_response(
        cls, xml: str, response_name: str = "BrowseResponse"
    ) -> BrowsePage:
        """Parse a Browse/Search SOAP response and its DIDL-Lite document."""
        root = parse_xml_string(xml)
        cls._raise_fault(root)

        if cls._find_element(root, response_name) is None:
            raise DlnaBrowseError(f"Invalid DLNA SOAP {response_name}")

        result = cls._find_text(root, "Result")
        total = cls._parse_int(cls._find_text(root, "TotalMatches"))
        returned = cls._parse_int(cls._find_text(root, "NumberReturned"))
        if not result:
            return BrowsePage([], returned or 0, total)

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

        if returned is None:
            returned = len(items)
        return BrowsePage(items, returned, total)

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
