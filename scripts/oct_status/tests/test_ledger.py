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
            body = json.loads(request.content)["body"]
            self.add_raw(body, updated=datetime.fromisoformat(json.loads(body)["ts"]))
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


async def test_no_strikes_before_activation_date():
    cfg = Config(automation={}, gate_checks=[], protected_paths=[], strikes_enabled_from=date(2026, 12, 1))
    fake = FakeLedgerIssue()
    ledger = make(fake, cfg=cfg)
    assert not ledger.active
    assert await ledger.record(violation()) is False
    assert await ledger.level_for("alice") == 0
    assert await ledger.ordinal("alice", 5, "V01", [(5, "V01")]) == 0
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


async def test_override_is_renewed_so_a_persisting_violation_is_not_charged_again():
    fake = FakeLedgerIssue()
    first = make(fake)
    await first.record(violation())
    await first.record_override("maintainer", 5, "known")
    # Day 40: too early to renew.
    assert await make(fake, Clock(NOW + timedelta(days=40))).renew_override(5) is False
    # Day 55: the override is older than window - 7 days, so it is renewed.
    day55 = make(fake, Clock(NOW + timedelta(days=55)))
    assert await day55.renew_override(5) is True
    assert await day55.renew_override(5) is False  # not twice
    assert await make(fake, Clock(NOW + timedelta(days=55))).renew_override(5) is False
    # Day 70: the original entries are gone, the renewal still covers the persisting violation.
    day70 = make(fake, Clock(NOW + timedelta(days=70)))
    assert await day70.is_overridden("alice", 5, "V01")
    assert await day70.record(violation()) is False
    assert await day70.level_for("alice") == 0
    assert await day70.renew_override(99) is False  # no override on that artifact
    # Without a renewal the same situation costs a strike.
    other = FakeLedgerIssue()
    await make(other).record(violation())
    await make(other).record_override("maintainer", 5, "known")
    day70 = make(other, Clock(NOW + timedelta(days=70)))
    assert await day70.record(violation()) is True and await day70.level_for("alice") == 1


async def test_ledger_bodies_never_contain_a_raw_at_sign_or_mention():
    fake = FakeLedgerIssue()
    ledger = make(fake)
    await ledger.record(violation())
    await ledger.record_override("maintainer", 5, "ping @gitar-bot and @someone")
    assert all("@" not in c["body"] and "gitar-bot" not in c["body"].lower() for c in fake.comments)
    assert all(isinstance(json.loads(c["body"]), dict) for c in fake.comments)
    # An escaped "@" round-trips through the parser.
    fake.add_raw(
        json.dumps(
            {"v": 1, "kind": "override", "user": "m", "artifact": 7, "ts": NOW.isoformat(), "reason": "a@b"}
        ).replace("@", "\\u0040")
    )
    entries = await make(fake).load()
    assert [e.reason for e in entries if e.artifact == 7] == ["a@b"]


async def test_ordinal_ranks_strikes_by_position():
    fake = FakeLedgerIssue()
    clock = Clock()
    ledger = make(fake, clock)
    await ledger.record(violation("V01", 1))
    clock.now += timedelta(hours=1)
    await ledger.record(violation("V01", 2))
    clock.now += timedelta(hours=1)
    await ledger.record(violation("V01", 3))
    assert [await ledger.ordinal("alice", n, "V01", []) for n in (1, 2, 3)] == [1, 2, 3]
    assert await ledger.ordinal("alice", 4, "V01", [(4, "V01"), (5, "V01")]) == 4
    assert await ledger.ordinal("alice", 5, "V01", [(4, "V01"), (5, "V01")]) == 5
    assert await ledger.ordinal("alice", 9, "V01", []) == 0  # not a counted strike
    await ledger.record_override("m", 2, "x")
    assert await ledger.ordinal("alice", 3, "V01", []) == 2  # the overridden strike no longer ranks
    cfg = Config(automation={}, gate_checks=[], protected_paths=[])
    assert await make(fake, cfg=cfg).ordinal("alice", 1, "V01", []) == 0  # strikes inactive


async def test_too_many_pages_fail_closed(monkeypatch):
    monkeypatch.setattr("oct_status.ledger._MAX_PAGES", 2)
    fake = FakeLedgerIssue()
    for n in range(1, 251):
        fake.add_raw("{}")
    with pytest.raises(LedgerError):
        await make(fake).level_for("alice")


async def test_override_covers_only_the_listed_strikes_not_later_ones():
    fake, clock = FakeLedgerIssue(), Clock()
    ledger = make(fake, clock)
    await ledger.record(violation("V01"))
    await ledger.record_override("maintainer", 5, "known")
    clock.now = NOW + timedelta(days=10)
    assert await ledger.record(violation("V04")) is True  # another rule on the same artifact counts
    assert await ledger.level_for("alice") == 1
    clock.now = NOW + timedelta(days=55)
    assert await ledger.renew_override(5) is True
    assert await ledger.level_for("alice") == 1  # the renewal does not swallow the V04 strike
    assert await ledger.is_overridden("alice", 5, "V01") and not await ledger.is_overridden("alice", 5, "V04")


async def test_override_is_scoped_to_the_users_it_listed():
    fake = FakeLedgerIssue()
    ledger = make(fake)
    await ledger.record(violation("V01", 5, "alice"))
    await ledger.record_override("maintainer", 5, "known")
    assert await ledger.record(violation("V01", 5, "bob")) is True  # the same rule by another user counts
    assert await ledger.level_for("bob") == 1 and await ledger.level_for("alice") == 0
    assert not await ledger.is_overridden("bob", 5, "V01")


async def test_covers_shape_is_validated_and_old_plain_lists_cover_nothing():
    fake = FakeLedgerIssue()
    base = {"v": 1, "user": "m", "artifact": 5, "ts": NOW.isoformat()}
    fake.add_raw(json.dumps({**base, "kind": "violation", "user": "alice", "rule": "V01"}))
    for covers in (
        ["V01"],
        [["alice"]],
        [["alice", "V99"]],
        [["a b", "V01"]],
        [[1, 2]],
        "V01",
        [["alice", "V01", "x"]],
    ):
        fake.add_raw(json.dumps({**base, "kind": "override", "covers": covers}))
    ledger = make(fake)
    assert await ledger.level_for("alice") == 1
    fake.add_raw(json.dumps({**base, "kind": "override", "covers": [["alice", "V01"]]}))
    assert await make(fake).level_for("alice") == 0
