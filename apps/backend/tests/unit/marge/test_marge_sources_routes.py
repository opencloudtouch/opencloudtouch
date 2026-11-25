"""Marge STORED_MUSIC source routes (speaker setMusicServiceAccount protocol, T11)."""

from unittest.mock import AsyncMock, MagicMock
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_marge_service
from opencloudtouch.main import app
from opencloudtouch.marge.service import MargeService
from opencloudtouch.marge.source_repository import MargeSourceRepository

UDN = "AbCdEf01-2222-3333-4444-555555555555"
BASE = "/streaming/account/acc1"
STREAMING_XML = "application/vnd.bose.streaming-v1.2+xml"


def _body(username=f"{UDN}/0", provider="7", name="NAS"):
    return (
        f"<source><credential></credential><username>{username}</username>"
        f"<sourceproviderid>{provider}</sourceproviderid>"
        f"<sourcename>{name}</sourcename></source>"
    )


@pytest.fixture
async def ctx(tmp_path):
    source_repo = MargeSourceRepository(str(tmp_path / "t.db"))
    await source_repo.initialize()
    device = MagicMock(device_id="DEV1", ip="192.0.2.50")
    device_repo = MagicMock()
    device_repo.get_by_account_uuid = AsyncMock(
        side_effect=lambda a: device if a == "acc1" else None
    )
    client = AsyncMock()
    factory = MagicMock(return_value=client)
    try:
        service = MargeService(
            MagicMock(),
            MagicMock(),
            device_repo,
            source_repo=source_repo,
            client_factory=factory,
        )
        app.dependency_overrides[get_marge_service] = lambda: service
        yield TestClient(app), client, source_repo, factory
    finally:
        app.dependency_overrides.pop(get_marge_service, None)
        await source_repo.close()


def _post(http, body=None, base=BASE):
    return http.post(f"{base}/source", content=_body() if body is None else body)


@pytest.mark.asyncio
async def test_post_registers_201_decision11_shape(ctx):
    http, _, repo, _ = ctx
    r = _post(http)
    assert r.status_code == 201
    assert r.headers["METHOD_NAME"] == "addSource"
    assert r.headers["content-type"].startswith(STREAMING_XML)
    root = ElementTree.fromstring(r.content)
    assert root.tag == "source" and root.attrib == {}
    assert [c.tag for c in root] == [
        "sourceID",
        "sourceProviderID",
        "createdOn",
        "updatedOn",
    ]
    assert int(root.findtext("sourceID")) >= 20000000
    assert root.findtext("sourceProviderID") == "7"
    assert root.findtext("createdOn").endswith("+00:00")
    stored = await repo.get("acc1", UDN)
    assert (stored.server_id, stored.display_name) == (UDN, "NAS")


@pytest.mark.asyncio
async def test_post_idempotent_same_id(ctx):
    http, _, _, _ = ctx
    a = ElementTree.fromstring(_post(http).content).findtext("sourceID")
    b = ElementTree.fromstring(_post(http, _body(name="Renamed")).content)
    assert b.findtext("sourceID") == a


@pytest.mark.asyncio
async def test_post_accepts_invalid_source_text(ctx):
    http, _, _, _ = ctx
    assert _post(http, _body(provider="INVALID_SOURCE")).status_code == 201


@pytest.mark.asyncio
async def test_post_bad_xml_400(ctx):
    http, _, _, _ = ctx
    for body in ("<source", "<x/>", _body(name=""), _body(name="a" * 65)):
        assert _post(http, body).status_code == 400


@pytest.mark.asyncio
async def test_post_username_without_slash_zero_400(ctx):
    http, _, _, _ = ctx
    assert _post(http, _body(username=UDN)).status_code == 400
    assert _post(http, _body(username="/0")).status_code == 400


@pytest.mark.asyncio
async def test_post_too_large_413(ctx):
    http, _, _, _ = ctx
    assert _post(http, _body(name="a" * 20000)).status_code == 413


@pytest.mark.asyncio
async def test_post_unknown_account_404(ctx):
    http, client, _, _ = ctx
    assert _post(http, base="/streaming/account/nope").status_code == 404
    client.notify_sources_updated.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_pushes_sources_updated_with_device_id(ctx):
    http, client, _, factory = ctx
    _post(http)
    factory.assert_called_once_with("http://192.0.2.50:8090")
    client.notify_sources_updated.assert_awaited_once_with("DEV1")
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_push_failure_does_not_fail_post(ctx):
    http, client, _, factory = ctx
    client.notify_sources_updated.side_effect = RuntimeError("down")
    assert _post(http).status_code == 201
    factory.side_effect = RuntimeError("no client")
    assert _post(http).status_code == 201


@pytest.mark.asyncio
async def test_delete_removes_and_idempotent(ctx):
    http, client, repo, _ = ctx
    sid = ElementTree.fromstring(_post(http).content).findtext("sourceID")
    r = http.delete(f"{BASE}/source/{sid}")
    assert r.status_code == 200 and r.headers["METHOD_NAME"] == "removeSource"
    assert r.content == b""
    assert await repo.list_for_account("acc1") == []
    assert client.notify_sources_updated.await_count == 2
    again = http.delete(f"{BASE}/source/{sid}")
    assert again.status_code == 200 and again.headers["METHOD_NAME"] == "removeSource"
    assert client.notify_sources_updated.await_count == 2


@pytest.mark.asyncio
async def test_get_sources_lists_stored(ctx):
    http, _, _, _ = ctx
    sid = ElementTree.fromstring(_post(http).content).findtext("sourceID")
    r = http.get(f"{BASE}/sources")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(STREAMING_XML)
    root = ElementTree.fromstring(r.content)
    assert root.tag == "sources"
    (src,) = root.findall("source")
    assert src.get("id") == sid
    assert src.findtext("sourceproviderid") == "7"
    assert src.findtext("username") == f"{UDN}/0"
    assert src.findtext("sourcename") == "NAS"
    empty = ElementTree.fromstring(http.get("/streaming/account/nope/sources").content)
    assert list(empty) == []
