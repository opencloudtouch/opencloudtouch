"""Relative TuneIn locations are resolved to real stream URLs (ICY probe input)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.bmx import tunein


@pytest.fixture(autouse=True)
def _clear_cache():
    tunein._stream_url_cache.clear()


def _response(url: str) -> MagicMock:
    return MagicMock(audio=MagicMock(streamUrl=url))


@pytest.mark.asyncio
async def test_absolute_url_is_unchanged(monkeypatch):
    resolver = AsyncMock()
    monkeypatch.setattr(tunein, "resolve_tunein_station", resolver)

    assert await tunein.resolve_tunein_location("http://x/stream") == "http://x/stream"
    resolver.assert_not_awaited()


@pytest.mark.asyncio
async def test_relative_location_is_resolved_and_cached(monkeypatch):
    resolver = AsyncMock(return_value=_response("http://radio/stream"))
    monkeypatch.setattr(tunein, "resolve_tunein_station", resolver)

    for _ in range(2):
        result = await tunein.resolve_tunein_location("/v1/playback/station/s158432")

    assert result == "http://radio/stream"
    resolver.assert_awaited_once_with("s158432")


@pytest.mark.asyncio
async def test_failed_resolve_returns_none(monkeypatch):
    monkeypatch.setattr(
        tunein, "resolve_tunein_station", AsyncMock(side_effect=ValueError("x"))
    )

    assert await tunein.resolve_tunein_location("/v1/playback/station/s1") is None
