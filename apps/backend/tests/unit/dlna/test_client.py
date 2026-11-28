"""Tests for the DLNA ContentDirectory client."""

import pytest

from opencloudtouch.dlna.client import DlnaBrowseError, DlnaClient

SOAP_RESPONSE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <u:BrowseResponse
        xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <Result>
        &lt;DIDL-Lite
          xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
          xmlns:dc="http://purl.org/dc/elements/1.1/"
          xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"&gt;
          &lt;container id="music" parentID="0"&gt;
            &lt;dc:title&gt;Music&lt;/dc:title&gt;
            &lt;upnp:class&gt;object.container.storageFolder&lt;/upnp:class&gt;
          &lt;/container&gt;
          &lt;item id="track-1" parentID="0"&gt;
            &lt;dc:title&gt;Test Track&lt;/dc:title&gt;
            &lt;upnp:class&gt;object.item.audioItem.musicTrack&lt;/upnp:class&gt;
            &lt;res protocolInfo="http-get:*:audio/mpeg:*"&gt;
              http://192.0.2.10:8200/media/track.mp3
            &lt;/res&gt;
          &lt;/item&gt;
        &lt;/DIDL-Lite&gt;
      </Result>
      <NumberReturned>2</NumberReturned>
      <TotalMatches>2</TotalMatches>
      <UpdateID>1</UpdateID>
    </u:BrowseResponse>
  </s:Body>
</s:Envelope>
"""


def test_build_browse_request():
    request = DlnaClient._build_browse_request("64$1&test")

    assert "<ObjectID>64$1&amp;test</ObjectID>" in request
    assert "<BrowseFlag>BrowseDirectChildren</BrowseFlag>" in request
    assert "<StartingIndex>0</StartingIndex>" in request
    assert "<RequestedCount>0</RequestedCount>" in request


def test_browse_page_parses_counts():
    page = DlnaClient._parse_browse_response(SOAP_RESPONSE)
    items = page.items
    assert (page.number_returned, page.total_matches) == (2, 2)

    assert len(items) == 2

    container = items[0]
    assert container.id == "music"
    assert container.parent_id == "0"
    assert container.title == "Music"
    assert container.is_container is True
    assert container.resource_url is None
    assert container.media_class == "object.container.storageFolder"

    track = items[1]
    assert track.id == "track-1"
    assert track.parent_id == "0"
    assert track.title == "Test Track"
    assert track.is_container is False
    assert track.resource_url == "http://192.0.2.10:8200/media/track.mp3"
    assert track.media_class == "object.item.audioItem.musicTrack"


def test_parse_empty_result():
    response = """<?xml version="1.0"?>
    <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
      <s:Body>
        <u:BrowseResponse
            xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
          <Result></Result>
        </u:BrowseResponse>
      </s:Body>
    </s:Envelope>
    """

    assert DlnaClient._parse_browse_response(response).items == []


def test_soap_fault_with_http_200_is_not_an_empty_folder():
    soap_fault = """<?xml version="1.0"?>
    <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
      <s:Body><s:Fault><faultcode>s:Client</faultcode>
        <faultstring>UPnPError</faultstring><detail>
          <UPnPError xmlns="urn:schemas-upnp-org:control-1-0">
            <errorCode>701</errorCode>
            <errorDescription>No Such Object</errorDescription>
          </UPnPError>
        </detail>
      </s:Fault></s:Body>
    </s:Envelope>"""
    with pytest.raises(DlnaBrowseError) as exc:
        DlnaClient._parse_browse_response(soap_fault)
    assert exc.value.error_code == "701"
    assert str(exc.value) == "No Such Object"


def test_missing_browse_response_is_not_empty_folder():
    with pytest.raises(DlnaBrowseError):
        DlnaClient._parse_browse_response("<Envelope><Body/></Envelope>")


@pytest.mark.asyncio
async def test_browse_surfaces_soap_fault_with_http_200():
    """HTTP 200 with a SOAP fault must raise DlnaBrowseError."""
    from unittest.mock import patch

    import httpx

    from opencloudtouch.dlna.models import DlnaServer

    server = DlnaServer(
        id="test-server",
        name="Test Server",
        location="http://192.168.55.30:8200/root.xml",
        control_url="http://192.168.55.30:8200/control",
    )

    fault = """<?xml version="1.0"?>
    <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
      <s:Body>
        <s:Fault>
          <faultcode>s:Client</faultcode>
          <faultstring>UPnPError</faultstring>
          <detail>
            <UPnPError xmlns="urn:schemas-upnp-org:control-1-0">
              <errorCode>701</errorCode>
              <errorDescription>No Such Object</errorDescription>
            </UPnPError>
          </detail>
        </s:Fault>
      </s:Body>
    </s:Envelope>"""

    def respond(request):
        return httpx.Response(200, text=fault)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    with patch(
        "opencloudtouch.dlna.client.httpx.AsyncClient",
        return_value=http_client,
    ):
        with pytest.raises(DlnaBrowseError) as exc:
            await DlnaClient().browse(server, "missing")

    assert exc.value.error_code == "701"
    assert str(exc.value) == "No Such Object"


@pytest.mark.asyncio
async def test_timeout_raises_timeout_error_and_sends_paging():
    from unittest.mock import patch

    import httpx

    from opencloudtouch.dlna.client import DlnaTimeoutError
    from opencloudtouch.dlna.models import DlnaServer

    server = DlnaServer("s", "N", "http://192.0.2.1/d", "http://192.0.2.1/c")
    seen = []

    def respond(request):
        seen.append(request.content.decode())
        raise httpx.ReadTimeout("slow")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    with patch(
        "opencloudtouch.dlna.client.httpx.AsyncClient", return_value=http_client
    ):
        with pytest.raises(DlnaTimeoutError):
            await DlnaClient().browse(server, "0", 100, 25)
    assert "<StartingIndex>100</StartingIndex>" in seen[0]
    assert "<RequestedCount>25</RequestedCount>" in seen[0]
