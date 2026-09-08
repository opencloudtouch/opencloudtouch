"""Tests for the DLNA ContentDirectory client."""

from opencloudtouch.dlna.client import DlnaClient

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


def test_parse_browse_response():
    items = DlnaClient._parse_browse_response(SOAP_RESPONSE)

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

    assert DlnaClient._parse_browse_response(response) == []
