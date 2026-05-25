"""Verified SoundTouch source types for Sources.xml generation.

Single source of truth for all source types that OCT writes into
Sources.xml — both the persistence file on the device and the Marge
boot-sync response.

Reference:
    https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/SoundTouch-WebServices-API#sources-list

BLUETOOTH is deliberately excluded: firmware manages it separately,
and including it breaks the physical source-cycle button.
"""

from dataclasses import dataclass

_TS_2012 = "2012-09-19T12:43:00.000+00:00"
_TS_2013 = "2013-01-01T00:00:00.000+00:00"
_TS_2014 = "2014-01-01T00:00:00.000+00:00"
_TS_2018 = "2018-01-01T00:00:00.000+00:00"


@dataclass(frozen=True)
class SourceType:
    """A SoundTouch source type entry."""

    streaming_id: str
    source_type: str
    display_name: str
    account: str
    secret_type: str
    created_on: str


BASE_SOURCES: list[SourceType] = [
    SourceType("42", "AIRPLAY", "AIRPLAY", "", "", _TS_2018),
    SourceType("41", "AUX", "AUX IN", "AUX", "", _TS_2013),
    SourceType("11", "LOCAL_INTERNET_RADIO", "LOCAL_INTERNET_RADIO", "", "token", _TS_2014),
    SourceType("53", "QPLAY", "QPLAY", "", "", _TS_2014),
    SourceType("30", "SPOTIFY", "SPOTIFY", "", "", "2014-06-01T00:00:00.000+00:00"),
    SourceType("50", "STORED_MUSIC", "STORED_MUSIC", "", "", _TS_2014),
    SourceType("51", "STORED_MUSIC_MEDIA_RENDERER", "STORED_MUSIC_MEDIA_RENDERER", "", "", _TS_2014),
    SourceType("25", "TUNEIN", "TUNEIN", "", "token", _TS_2012),
    SourceType("52", "UPNP", "UPNP", "", "", _TS_2014),
]
