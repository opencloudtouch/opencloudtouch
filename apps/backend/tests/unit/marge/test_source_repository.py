"""Persistence tests for Marge media server sources keyed by account."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from opencloudtouch.marge.source_repository import (
    FIRST_SOURCE_ID,
    MargeSourceRepository,
)


@pytest.fixture
async def repo(tmp_path):
    repository = MargeSourceRepository(tmp_path / "sources.db")
    await repository.initialize()
    try:
        yield repository
    finally:
        await repository.close()


async def test_first_id_is_20000000(repo):
    source = await repo.upsert("account-a", "server-a", "Music")
    assert source.source_id == FIRST_SOURCE_ID == 20000000
    assert source.account_id == "account-a"
    assert source.display_name == "Music"
    assert source.account == "server-a/0"
    assert source.created_at.tzinfo == UTC
    assert source.created_at == source.updated_at
    assert await repo.get("account-a", "server-a") == source
    assert await repo.get_by_id("account-a", source.source_id) == source
    assert await repo.get_by_id("account-b", source.source_id) is None
    with pytest.raises(FrozenInstanceError):
        source.display_name = "Changed"  # type: ignore[misc]


async def test_upsert_keeps_id(repo):
    with patch(
        "opencloudtouch.marge.source_repository.datetime", wraps=datetime
    ) as clock:
        clock.now.return_value = datetime(2026, 1, 1, tzinfo=UTC)
        original = await repo.upsert("account-a", "uuid:Server-A", "Old")
        clock.now.return_value = datetime(2026, 1, 2, tzinfo=UTC)
        updated = await repo.upsert("account-a", "Server-A", "New")
    assert updated.source_id == original.source_id
    assert updated.created_at == original.created_at
    assert updated.updated_at > original.updated_at
    assert updated.display_name == "New"
    assert await repo.list_for_account("account-a") == [updated]


async def test_server_id_case_kept_prefix_removed(repo):
    source = await repo.upsert("account-a", "uuid:AbC-123", "Music")
    assert source.server_id == "AbC-123"
    assert source.account == "AbC-123/0"
    assert await repo.get("account-a", "uuid:AbC-123") == source
    assert await repo.get("account-a", "AbC-123") == source
    # Case is kept, so another spelling is another server (decision 48).
    assert await repo.get("account-a", "abc-123") is None


async def test_list_scoped_by_account_and_ordered(repo):
    first = await repo.upsert("account-a", "server-z", "First")
    other = await repo.upsert("account-b", "server-y", "Other account")
    last = await repo.upsert("account-a", "server-a", "Last")
    assert await repo.list_for_account("account-a") == [first, last]
    assert await repo.list_for_account("account-b") == [other]
    assert await repo.list_for_account("missing") == []


async def test_two_accounts_same_server_are_separate_rows(repo):
    a = await repo.upsert("account-a", "server-a", "Music")
    b = await repo.upsert("account-b", "server-a", "Music")
    assert a.source_id != b.source_id
    assert await repo.get("account-b", "server-a") == b


async def test_delete_idempotent(repo):
    source = await repo.upsert("account-a", "server-a", "Music")
    other = await repo.upsert("account-b", "server-a", "Other")
    assert await repo.delete("account-b", source.source_id) is False
    assert await repo.delete("account-a", source.source_id) is True
    assert await repo.delete("account-a", source.source_id) is False
    assert await repo.get("account-b", "server-a") == other


async def test_ids_not_reused(repo):
    first = await repo.upsert("account-a", "server-a", "Music")
    await repo.delete("account-a", first.source_id)
    second = await repo.upsert("account-a", "server-a", "Music")
    assert second.source_id > first.source_id


async def test_migrations_idempotent(tmp_path):
    path = tmp_path / "sources.db"
    repo = MargeSourceRepository(path)
    await repo.initialize()
    try:
        first = await repo.upsert("account-a", "server-a", "Music")
        await repo.delete("account-a", first.source_id)
    finally:
        await repo.close()
    reopened = MargeSourceRepository(path)
    await reopened.initialize()
    try:
        second = await reopened.upsert("account-a", "server-a", "Music")
        assert second.source_id > first.source_id
        async with reopened._conn.execute(
            "SELECT version FROM schema_versions ORDER BY version"
        ) as cursor:
            assert [row[0] for row in await cursor.fetchall()] == [500, 501]
    finally:
        await reopened.close()
