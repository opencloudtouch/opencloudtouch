"""Tests for the strike ledger: window, dedupe, overrides, exemptions, validation and failure modes."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from oct_status.api import GitHubApi
from oct_status.config import Config
from oct_status.ledger import Ledger, LedgerError
from oct_status.violations import Violation

REPO = "o/r"
ISSUE = 99
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class FakeLedgerIssue:
    """Comments of the ledger issue; honours `since` and pages like GitHub."""

    def __init__(self) -> None:
        self.comments: list[dict] = []
        self.fail_read = False
        self.fail_write = False
        self.posts = 0

    def add_raw(self, body: str, login: str = "oct-support", updated: datetime = NOW) -> None:
        self.comments.append(
            {"id": len(self.comments) + 1, "body": body, "user": {"login": login}, "updated_at": updated.isoformat()}
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/repos/{REPO}/issues/{ISSUE}/comments"
        if request.method == "POST":
            if self.fail_write:
                return httpx.Response(500, json={})
            self.posts += 1
            self.add_raw(json.loads(request.content)["body"])
            return httpx.Response(201, json={})
        if self.fail_read:
            return httpx.Response(500, json={})
        since = datetime.fromisoformat(request.url.params["since"].replace("Z", "+00:00"))
        page, per_page = int(request.url.params["page"]), int(request.url.params["per_page"])
        rows = [c for c in self.comments if datetime.fromisoformat(c["updated_at"]) >= since]
        return httpx.Response(200, json=rows[(page - 1) * per_page : page * per_page])


def make(fake: FakeLedgerIssue, clock: Clock | None = None, **kw) -> Ledger:
    api = GitHubApi("t", REPO, transport=httpx.MockTransport(fake.handler), sleep=_nosleep)
    return Ledger(api, ISSUE, clock or Clock(), **kw)


async def _nosleep(_: float) -> None:
    return None


def violation(rule: str = "V01", artifact: int = 5, user: str = "alice") -> Violation:
    return Violation(rule, artifact, user, "hint")


async def test_level_counts_distinct_artifact_rule_pairs_in_60_days():
    fake, clock = FakeLedgerIssue(), Clock()
    ledger = make(fake, clock)
    assert await ledger.record(violation()) is True
    assert await ledger.record(violation()) is False  # the same pair again is not a second strike
    assert await ledger.level_for("alice") == 1
    assert fake.posts == 1
    await ledger.record(violation("V06"))
    assert await ledger.level_for("alice") == 2
    assert await ledger.level_for("bob") == 0
    later = make(fake, Clock(NOW + timedelta(days=61)))  # a fresh run 61 days later
    assert await later.level_for("alice") == 0
    inside = make(fake, Clock(NOW + timedelta(days=59)))
    assert await inside.level_for("alice") == 2


async def test_dedupe_survives_a_new_run():
    fake = FakeLedgerIssue()
    await make(fake).record(violation())
    assert await make(fake).record(violation()) is False
    assert fake.posts == 1


async def test_override_not_counted():
    fake = FakeLedgerIssue()
    ledger = make(fake)
    await ledger.record(violation())
    await ledger.record(violation("V06", artifact=6))
    await ledger.record_override("maintainer", 5, "false positive")
    assert await ledger.level_for("alice") == 1
    assert await ledger.is_overridden("alice", 5, "V01")
    assert not await ledger.is_overridden("alice", 6, "V06")
    # The override is in the ledger as its own entry, and the overridden pair is not recorded again.
    assert any('"kind": "override"' in c["body"] for c in fake.comments)
    assert await ledger.record(violation()) is False
    # A new rule on the overridden artifact counts again.
    clock = Clock(NOW + timedelta(hours=1))
    assert await make(fake, clock).record(violation("V06", artifact=5)) is True
    assert await make(fake, clock).level_for("alice") == 2


async def test_level_after_previews_without_writing():
    fake = FakeLedgerIssue()
    ledger = make(fake)
    await ledger.record(violation())
    assert await ledger.level_after("alice", {(5, "V01"), (7, "V02")}) == 2
    assert fake.posts == 1


async def test_no_strikes_before_activation_date():
    cfg = Config(automation={}, gate_checks=[], protected_paths=[], strikes_enabled_from=date(2026, 12, 1))
    fake = FakeLedgerIssue()
    ledger = make(fake, cfg=cfg)
    assert not ledger.active
    assert await ledger.record(violation()) is False
    assert await ledger.level_for("alice") == 0
    assert await ledger.level_after("alice", {(5, "V01")}) == 0
    assert fake.posts == 0
    active = make(fake, Clock(datetime(2026, 12, 1, tzinfo=UTC)), cfg=cfg)
    assert active.active and await active.record(violation()) is True
    unset = Config(automation={}, gate_checks=[], protected_paths=[])
    assert not make(fake, cfg=unset).active


async def test_cfg_window_days_is_used():
    cfg = Config(
        automation={}, gate_checks=[], protected_paths=[], strike_window_days=10, strikes_enabled_from=date(2026, 1, 1)
    )
    fake = FakeLedgerIssue()
    await make(fake, cfg=cfg).record(violation())
    assert await make(fake, Clock(NOW + timedelta(days=11)), cfg=cfg).level_for("alice") == 0


async def test_malformed_and_foreign_entries_are_ignored():
    fake = FakeLedgerIssue()
    good = {"v": 1, "kind": "violation", "user": "alice", "artifact": 5, "rule": "V01", "ts": NOW.isoformat()}
    fake.add_raw(json.dumps(good))
    fake.add_raw("not json")
    fake.add_raw("[1, 2]")
    fake.add_raw(json.dumps({**good, "v": 2}))
    fake.add_raw(json.dumps({**good, "rule": "V99"}))
    fake.add_raw(json.dumps({**good, "kind": "other"}))
    fake.add_raw(json.dumps({**good, "user": "a b; rm"}))
    fake.add_raw(json.dumps({**good, "artifact": True}))
    fake.add_raw(json.dumps({**good, "artifact": -3}))
    fake.add_raw(json.dumps({**good, "ts": "yesterday"}))
    fake.add_raw(json.dumps({**good, "ts": "2026-11-01T10:00:00"}))  # no time zone
    fake.add_raw(json.dumps({**good, "ts": (NOW + timedelta(days=30)).isoformat()}))  # from the future
    fake.add_raw(json.dumps({**good, "kind": "override", "rule": "V01"}))  # an override carries no rule
    fake.add_raw(json.dumps({**good, "artifact": 6}), login="mallory")  # not written by the automation
    ledger = make(
        fake, cfg=Config(automation={}, gate_checks=[], protected_paths=[], strikes_enabled_from=date(2026, 1, 1))
    )
    assert await ledger.level_for("alice") == 1


async def test_second_page_is_read():
    fake = FakeLedgerIssue()
    for n in range(1, 131):
        fake.add_raw(
            json.dumps(
                {"v": 1, "kind": "violation", "user": "alice", "artifact": n, "rule": "V01", "ts": NOW.isoformat()}
            )
        )
    assert await make(fake).level_for("alice") == 130


async def test_unreadable_ledger_raises_ledger_error():
    fake = FakeLedgerIssue()
    fake.fail_read = True
    with pytest.raises(LedgerError):
        await make(fake).level_for("alice")


async def test_unwritable_ledger_raises_ledger_error():
    fake = FakeLedgerIssue()
    fake.fail_write = True
    with pytest.raises(LedgerError):
        await make(fake).record(violation())
    with pytest.raises(LedgerError):
        await make(fake).record_override("m", 5, "why")
