"""Provider ids in /full stay version-gated (decisions 14, 15, 20; T14b)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.core.source_types import BASE_SOURCES
from opencloudtouch.marge.service import MargeService
from opencloudtouch.marge.source_repository import MediaServerSource
from opencloudtouch.marge.xml_builder import build_streaming_account_xml

UDN = "AbCdEf01-2222-3333-4444-555555555555"
NOW = datetime(2026, 11, 1, tzinfo=UTC)

# (source id, provider id, name) as served by main (2.1.0) - pinned by T14b.
MAIN_DEFAULTS = [
    ("42", "42", "AIRPLAY"),
    ("41", "41", "AUX"),
    ("11", "11", "LOCAL_INTERNET_RADIO"),
    ("53", "53", "QPLAY"),
    ("30", "30", "SPOTIFY"),
    ("50", "50", "STORED_MUSIC"),
    ("51", "51", "STORED_MUSIC_MEDIA_RENDERER"),
    ("25", "25", "TUNEIN"),
    ("52", "52", "UPNP"),
]
CHILD_ORDER = [
    "createdOn",
    "credential",
    "name",
    "sourceproviderid",
    "sourcename",
    "sourceSettings",
    "updatedOn",
    "username",
]


def _stored(source_id=20000000):
    return MediaServerSource(source_id, "acc1", UDN, "NAS", NOW, NOW)


def _rows(account):
    return [
        (s.get("id"), s.findtext("sourceproviderid"), s.findtext("name"))
        for s in account.findall("./sources/source")
    ]


def test_version_zero_keeps_old_provider_ids():
    account = build_streaming_account_xml("acc1")
    assert _rows(account) == MAIN_DEFAULTS
    for source in account.findall("./sources/source"):
        assert [child.tag for child in source] == CHILD_ORDER


def test_version_one_uses_catalogue_ids():
    rows = _rows(build_streaming_account_xml("acc1", catalogue_ids=True))
    providers = {name: provider for _, provider, name in rows}
    assert providers == {
        "AIRPLAY": "5",
        "AUX": "9",
        "LOCAL_INTERNET_RADIO": "11",
        "QPLAY": "26",
        "SPOTIFY": "15",
        "STORED_MUSIC": "7",
        "STORED_MUSIC_MEDIA_RENDERER": "51",
        "TUNEIN": "25",
        "UPNP": "52",
    }
    # The source ids stay the old ids; only the provider ids switch.
    assert [row[0] for row in rows] == [row[0] for row in MAIN_DEFAULTS]


def test_stored_server_follows_default_stored_music_provider_and_udn_account():
    """Version 0 serves the old STORED_MUSIC id 50 for stored servers too (T20)."""
    account = build_streaming_account_xml("acc1", stored_sources=[_stored()])
    assert _rows(account)[:-1] == MAIN_DEFAULTS
    stored = account.findall("./sources/source")[-1]
    assert stored.get("id") == "20000000"
    assert stored.findtext("sourceproviderid") == "50"
    assert stored.findtext("username") == f"{UDN}/0"
    assert stored.findtext("name") == f"{UDN}/0"
    assert stored.findtext("sourcename") == "NAS"
    assert [child.tag for child in stored] == CHILD_ORDER


def test_stored_server_uses_catalogue_id_7_on_version_one():
    account = build_streaming_account_xml(
        "acc1", stored_sources=[_stored()], catalogue_ids=True
    )
    stored = account.findall("./sources/source")[-1]
    assert stored.findtext("sourceproviderid") == "7"


def test_defaults_unchanged_without_stored_sources():
    assert _rows(build_streaming_account_xml("acc1", stored_sources=[])) == (
        MAIN_DEFAULTS
    )


@pytest.mark.parametrize("catalogue_ids", [False, True])
def test_pseudo_sources_still_served(catalogue_ids):
    names = {
        row[2]
        for row in _rows(
            build_streaming_account_xml("acc1", catalogue_ids=catalogue_ids)
        )
    }
    assert {"UPNP", "STORED_MUSIC_MEDIA_RENDERER"} <= names


def test_provider_ids_follow_the_catalogue():
    assert {s.source_type: s.provider_id for s in BASE_SOURCES}["AUX"] == "9"


def _service(stored=None):
    preset_repo = MagicMock()
    preset_repo.get_preset = AsyncMock(return_value=None)
    preset_repo.set_preset = AsyncMock(side_effect=lambda preset: preset)
    device_repo = MagicMock()
    device_repo.get_by_device_id = AsyncMock(
        return_value=MagicMock(marge_account_uuid="acc1")
    )
    source_repo = MagicMock()
    source_repo.get_by_id = AsyncMock(return_value=stored)
    service = MargeService(preset_repo, MagicMock(), device_repo, source_repo)
    return service, source_repo


@pytest.mark.asyncio
async def test_store_preset_maps_stored_source_id():
    service, source_repo = _service(_stored())

    preset = await service.store_preset("DEV1", 2, "20000000", "Album", "1$4$12 TRACK")

    assert preset.source == "STORED_MUSIC"
    source_repo.get_by_id.assert_awaited_once_with("acc1", 20000000)


@pytest.mark.asyncio
async def test_store_preset_keeps_unknown_id():
    service, _ = _service(None)

    preset = await service.store_preset("DEV1", 2, "20000099", "X", "loc")

    assert preset.source == "20000099"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_id", "expected"),
    [("41", "AUX"), ("25", "TUNEIN"), ("50", "STORED_MUSIC"), ("42", "AIRPLAY")],
)
async def test_store_preset_maps_old_ids(source_id, expected):
    service, source_repo = _service(_stored())

    preset = await service.store_preset("DEV1", 1, source_id, "X", "/loc")

    assert preset.source == expected
    source_repo.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_store_preset_skips_lookup_for_non_numeric_id():
    service, source_repo = _service(_stored())

    preset = await service.store_preset("DEV1", 1, "INVALID_SOURCE", "X", "/loc")

    assert preset.source == "INVALID_SOURCE"
    source_repo.get_by_id.assert_not_awaited()


def test_full_without_migration_service_in_state_means_version_zero():
    from types import SimpleNamespace

    from opencloudtouch.marge.routes import _migration_service

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    assert _migration_service(request) is None
