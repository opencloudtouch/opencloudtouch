"""Tests for the shared DLNA preset reference helper (AC-B3, AC-B15)."""

import base64
import json
import re

import pytest

from opencloudtouch.core.dlna_reference import (
    DLNA_LOCATION_MAX_LENGTH,
    DLNA_NAME_MAX,
    DLNA_OBJECT_ID_MAX,
    DlnaReference,
    DlnaReferenceTooLongError,
    build_orion_data,
    build_orion_location,
    from_station_url,
    parse_orion_data,
    station_uuid,
    to_station_url,
)

IDS = [
    "plain",
    "with space",
    "a/b/c",
    "a&b=c?d#e",
    "100%25 literal %",
    "Übergöße – 日本語 \U0001f3b5",
    "x" * 512,
    "ü" * 512,
]


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode()


@pytest.mark.parametrize("object_id", IDS)
def test_station_url_round_trip(object_id):
    ref = DlnaReference("0a1b-udn", object_id)
    url = to_station_url(ref)
    assert url.startswith("dlna://")
    assert from_station_url(url) == ref


@pytest.mark.parametrize("object_id", IDS)
def test_orion_data_round_trip(object_id):
    ref = DlnaReference("0a1b-udn", object_id)
    assert parse_orion_data(build_orion_data(ref, "Titel ü")) == (
        ref,
        "Titel ü",
    )


@pytest.mark.parametrize(
    "url", ["http://x", "", "dlna://", "dlna://server", "dlna://server/", "dlna:///x"]
)
def test_from_station_url_rejects_non_dlna(url):
    assert from_station_url(url) is None


def test_station_uuid_is_deterministic_and_well_formed():
    a = station_uuid(DlnaReference("s", "o"))
    assert a == station_uuid(DlnaReference("s", "o"))
    assert re.fullmatch(r"dlna-[0-9a-f]{16}", a)
    assert a != station_uuid(DlnaReference("s", "p"))
    # the separator keeps ("ab", "c") apart from ("a", "bc")
    assert station_uuid(DlnaReference("ab", "c")) != station_uuid(
        DlnaReference("a", "bc")
    )


def test_orion_data_has_no_url_fields_and_truncates_name():
    data = build_orion_data(DlnaReference("s", "o"), "n" * 300)
    payload = json.loads(base64.urlsafe_b64decode(data))
    assert set(payload) == {"dlna", "name"}
    assert payload["dlna"] == {"server_id": "s", "object_id": "o"}
    assert len(payload["name"]) == 200


def test_orion_data_keeps_non_ascii_unescaped():
    data = build_orion_data(DlnaReference("s", "ü"), "ö")
    assert "ü" in base64.urlsafe_b64decode(data).decode("utf-8")


@pytest.mark.parametrize(
    "data",
    [
        "",
        "!!!",
        _b64(b"not json"),
        _b64(b'{"streamUrl":"http://x"}'),
        _b64(b'{"dlna":"x"}'),
        _b64(b'{"dlna":{"server_id":"s"}}'),
        _b64(b'{"dlna":{"server_id":"","object_id":"o"}}'),
        _b64(b'{"dlna":{"server_id":1,"object_id":"o"}}'),
        _b64(b"[1]"),
    ],
)
def test_parse_orion_data_rejects_garbage(data):
    assert parse_orion_data(data) is None


def test_parse_orion_data_tolerates_stripped_padding():
    data = build_orion_data(DlnaReference("s", "o"), "N").rstrip("=")
    assert parse_orion_data(data) == (DlnaReference("s", "o"), "N")


def test_parse_orion_data_without_name_yields_empty_name():
    data = _b64(b'{"dlna":{"server_id":"s","object_id":"o"}}')
    assert parse_orion_data(data) == (DlnaReference("s", "o"), "")


def test_location_within_limit():
    loc = build_orion_location(
        "http://oct.local:7777", DlnaReference("s", "o"), "T", enforce_limit=True
    )
    assert loc.startswith("http://oct.local:7777/core02/svc-bmx-adapter-orion/")
    assert "?data=" in loc
    assert len(loc) <= DLNA_LOCATION_MAX_LENGTH


def test_location_worst_case_non_ascii_is_rejected():
    ref = DlnaReference("0a1b2c3d-0000-1111-2222-333344445555", "ü" * 512)
    name = "ö" * 200
    with pytest.raises(DlnaReferenceTooLongError):
        build_orion_location("http://oct.local:7777", ref, name, enforce_limit=True)
    # rendering an already stored row (marge) must not raise
    assert build_orion_location("http://oct.local:7777", ref, name)


def test_limit_constants():
    assert DLNA_LOCATION_MAX_LENGTH == 1024
    assert DLNA_OBJECT_ID_MAX == 512
    assert DLNA_NAME_MAX == 200
