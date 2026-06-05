"""Tests for WebSocket XML event parser."""

from __future__ import annotations

from opencloudtouch.devices.websocket.parser import (
    EventType,
    _parse_now_playing,
    _parse_volume,
    parse_event,
)

# ---------------------------------------------------------------------------
# Real XML samples from doc/02-websocket-events.md
# ---------------------------------------------------------------------------

NOW_PLAYING_XML = """\
<?xml version="1.0" encoding="UTF-8" ?>
<updates deviceID="689E19B8BB8A">
    <nowPlayingUpdated deviceID="689E19B8BB8A">
        <nowPlaying deviceID="689E19B8BB8A" source="SPOTIFY">
            <track>Song Title</track>
            <artist>Artist Name</artist>
            <album>Album Name</album>
            <playStatus>PLAY_STATE</playStatus>
            <stationName>My Playlist</stationName>
            <art>https://example.com/art.jpg</art>
        </nowPlaying>
    </nowPlayingUpdated>
</updates>"""

VOLUME_XML = """\
<?xml version="1.0" encoding="UTF-8" ?>
<updates deviceID="AABBCCDDEEFF">
    <volumeUpdated deviceID="AABBCCDDEEFF">
        <volume>
            <targetvolume>50</targetvolume>
            <actualvolume>48</actualvolume>
            <muteenabled>false</muteenabled>
        </volume>
    </volumeUpdated>
</updates>"""

VOLUME_MUTED_XML = """\
<updates deviceID="AABBCCDDEEFF">
    <volumeUpdated deviceID="AABBCCDDEEFF">
        <volume>
            <targetvolume>0</targetvolume>
            <actualvolume>0</actualvolume>
            <muteenabled>true</muteenabled>
        </volume>
    </volumeUpdated>
</updates>"""

PRESETS_XML = """\
<updates deviceID="112233445566">
    <presetsUpdated deviceID="112233445566">
        <preset id="1">
            <ContentItem source="SPOTIFY">
                <itemName>My Playlist</itemName>
            </ContentItem>
        </preset>
    </presetsUpdated>
</updates>"""

ZONE_XML = """\
<updates deviceID="AABB11223344">
    <zoneUpdated deviceID="AABB11223344">
        <zone master="ABCD1234EFGH">
            <member ipaddress="192.168.1.11">EFGH5678IJKL</member>
        </zone>
    </zoneUpdated>
</updates>"""

CONNECTION_XML = """\
<updates deviceID="FFEEDDCCBBAA">
    <connectionStateUpdated deviceID="FFEEDDCCBBAA">
        <info>connected</info>
    </connectionStateUpdated>
</updates>"""

BASS_XML = """\
<updates deviceID="001122334455">
    <bassUpdated deviceID="001122334455">
        <bass>
            <targetbass>-3</targetbass>
            <actualbass>-3</actualbass>
        </bass>
    </bassUpdated>
</updates>"""


# ---------------------------------------------------------------------------
# parse_event — happy paths
# ---------------------------------------------------------------------------


class TestParseEventHappyPaths:
    def test_now_playing_event(self):
        event = parse_event(NOW_PLAYING_XML)
        assert event is not None
        assert event.device_id == "689E19B8BB8A"
        assert event.event_type == EventType.NOW_PLAYING
        assert event.now_playing is not None
        assert event.now_playing.source == "SPOTIFY"
        assert event.now_playing.state == "PLAY_STATE"
        assert event.now_playing.track == "Song Title"
        assert event.now_playing.artist == "Artist Name"
        assert event.now_playing.album == "Album Name"
        assert event.now_playing.station_name == "My Playlist"
        assert event.now_playing.artwork_url == "https://example.com/art.jpg"
        assert event.volume is None

    def test_volume_event(self):
        event = parse_event(VOLUME_XML)
        assert event is not None
        assert event.device_id == "AABBCCDDEEFF"
        assert event.event_type == EventType.VOLUME
        assert event.volume is not None
        assert event.volume.target == 50
        assert event.volume.actual == 48
        assert event.volume.muted is False
        assert event.now_playing is None

    def test_volume_muted(self):
        event = parse_event(VOLUME_MUTED_XML)
        assert event is not None
        assert event.volume is not None
        assert event.volume.muted is True
        assert event.volume.target == 0
        assert event.volume.actual == 0

    def test_presets_event(self):
        event = parse_event(PRESETS_XML)
        assert event is not None
        assert event.device_id == "112233445566"
        assert event.event_type == EventType.PRESETS
        assert event.now_playing is None
        assert event.volume is None

    def test_zone_event(self):
        event = parse_event(ZONE_XML)
        assert event is not None
        assert event.event_type == EventType.ZONE

    def test_connection_event(self):
        event = parse_event(CONNECTION_XML)
        assert event is not None
        assert event.event_type == EventType.CONNECTION

    def test_bass_event(self):
        event = parse_event(BASS_XML)
        assert event is not None
        assert event.event_type == EventType.BASS

    def test_raw_xml_preserved(self):
        event = parse_event(VOLUME_XML)
        assert event is not None
        assert event.raw_xml == VOLUME_XML

    def test_timestamp_set(self):
        event = parse_event(VOLUME_XML)
        assert event is not None
        assert event.timestamp is not None

    def test_device_id_extraction(self):
        event = parse_event(BASS_XML)
        assert event is not None
        assert event.device_id == "001122334455"


# ---------------------------------------------------------------------------
# parse_event — error cases
# ---------------------------------------------------------------------------


class TestParseEventErrors:
    def test_malformed_xml(self):
        assert parse_event("<not valid xml><<<") is None

    def test_empty_string(self):
        assert parse_event("") is None

    def test_whitespace_only(self):
        assert parse_event("   \n  ") is None

    def test_wrong_root_element(self):
        assert parse_event("<info><name>test</name></info>") is None

    def test_missing_device_id(self):
        assert parse_event("<updates><volumeUpdated/></updates>") is None

    def test_empty_updates_element(self):
        event = parse_event('<updates deviceID="AAA"></updates>')
        assert event is not None
        assert event.event_type == EventType.UNKNOWN
        assert event.device_id == "AAA"

    def test_unknown_event_type(self):
        xml = '<updates deviceID="AAA"><somethingNew/></updates>'
        event = parse_event(xml)
        assert event is not None
        assert event.event_type == EventType.UNKNOWN


# ---------------------------------------------------------------------------
# _parse_now_playing — edge cases
# ---------------------------------------------------------------------------


class TestParseNowPlaying:
    def test_missing_nowplaying_child(self):
        """<nowPlayingUpdated> without <nowPlaying> child."""
        from defusedxml import ElementTree as ET

        el = ET.fromstring("<nowPlayingUpdated/>")
        result = _parse_now_playing(el)
        assert result.source == "UNKNOWN"
        assert result.state == "STOP_STATE"

    def test_minimal_nowplaying(self):
        from defusedxml import ElementTree as ET

        xml = '<nowPlayingUpdated><nowPlaying source="AUX"><playStatus>STOP_STATE</playStatus></nowPlaying></nowPlayingUpdated>'
        el = ET.fromstring(xml)
        result = _parse_now_playing(el)
        assert result.source == "AUX"
        assert result.state == "STOP_STATE"
        assert result.track is None
        assert result.artist is None
        assert result.album is None
        assert result.artwork_url is None
        assert result.station_name is None

    def test_empty_text_fields(self):
        from defusedxml import ElementTree as ET

        xml = '<nowPlayingUpdated><nowPlaying source="BT"><track></track><artist></artist></nowPlaying></nowPlayingUpdated>'
        el = ET.fromstring(xml)
        result = _parse_now_playing(el)
        assert result.track is None
        assert result.artist is None


# ---------------------------------------------------------------------------
# _parse_volume — edge cases
# ---------------------------------------------------------------------------


class TestParseVolume:
    def test_missing_volume_child(self):
        from defusedxml import ElementTree as ET

        el = ET.fromstring("<volumeUpdated/>")
        result = _parse_volume(el)
        assert result.actual == 0
        assert result.target == 0
        assert result.muted is False

    def test_non_numeric_volume(self):
        from defusedxml import ElementTree as ET

        xml = "<volumeUpdated><volume><targetvolume>abc</targetvolume><actualvolume>xyz</actualvolume><muteenabled>false</muteenabled></volume></volumeUpdated>"
        el = ET.fromstring(xml)
        result = _parse_volume(el)
        assert result.target == 0
        assert result.actual == 0


# ---------------------------------------------------------------------------
# Regression: known non-event root elements and new event tags
# ---------------------------------------------------------------------------


class TestKnownWebSocketEvents:
    """Regression: SoundTouchSdkInfo, userActivityUpdate logged as WARNING;
    nowSelectionUpdated, recentsUpdated logged as 'unknown event tag'."""

    def test_now_selection_updated_ignored_as_unknown(self):
        """nowSelectionUpdated has no <nowPlaying> child in real devices.

        It must NOT be treated as NOW_PLAYING because it creates fake STOP
        events that clear the frontend's now-playing state.
        Regression: https://github.com/.../issues/184
        """
        xml = """\
<updates deviceID="AABB11223344">
    <nowSelectionUpdated deviceID="AABB11223344">
        <nowPlaying source="TUNEIN">
            <stationName>NDR 2</stationName>
            <playStatus>PLAY_STATE</playStatus>
            <art>http://cdn-profiles.tunein.com/logo.png</art>
        </nowPlaying>
    </nowSelectionUpdated>
</updates>"""
        event = parse_event(xml)
        assert event is not None
        assert event.event_type == EventType.UNKNOWN
        assert event.now_playing is None

    def test_recents_updated_parsed_as_presets(self):
        xml = '<updates deviceID="AABB11223344"><recentsUpdated/></updates>'
        event = parse_event(xml)
        assert event is not None
        assert event.event_type == EventType.PRESETS

    def test_soundtouch_sdk_info_ignored_silently(self):
        xml = '<SoundTouchSdkInfo serverVersion="4" serverBuild="trunk"/>'
        event = parse_event(xml)
        assert event is None

    def test_user_activity_update_ignored_silently(self):
        xml = '<userActivityUpdate deviceID="AABB">{}</userActivityUpdate>'
        event = parse_event(xml)
        assert event is None

    def test_unknown_root_element_still_returns_none(self):
        xml = "<totallyUnknownElement/>"
        event = parse_event(xml)
        assert event is None
