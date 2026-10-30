"""Persistent notices in the guide's oct-next-data, and level-3 enforcement (revert on issues, red check on PRs)."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import timedelta

import httpx
import pytest

from oct_status.apply import MARKER
from oct_status.guide import WORKFLOW
from oct_status.main import run_check, run_event
from oct_status.notices import DATA_BUDGET, MAX_OPEN, Record, parse_state, render, scrub, state_data

from .test_commands import comment_event
from .test_main_events import _nosleep, api_for
from .test_rules import DOR_DONE
from .test_violations_events import ACTIVE, NOW, Repo, pr_event, run, seed

TEMPLATE = DOR_DONE + "\n## Acceptance criteria\n- [ ] AC1: works\n"


def data(repo: Repo, number: int) -> dict:
    return json.loads(re.search(r"<!-- oct-next-data (.*) -->", repo.guide(number))[1])


def open_rules(repo: Repo, number: int) -> list[str]:
    return [n["rule"] for n in data(repo, number).get("notices", []) if not n["resolved"]]


async def run_at(repo: Repo, event: str, payload: dict, when, cfg=ACTIVE) -> None:
    api = api_for(repo)
    assert await run_event(api, cfg, event, payload, dry_run=False, clock=lambda: when) == 0
    await api.aclose()


async def check(repo: Repo, number: int) -> int:
    api = api_for(repo)
    try:
        return await run_check(api, ACTIVE, "pull_request_target", pr_event(number, "synchronize"))
    finally:
        await api.aclose()


def spec_edit(repo: Repo, number: int, new_body: str, sender: str = "bob") -> dict:
    before = repo.issues[number]["body"]
    repo.issues[number]["body"] = new_body
    return {
        "action": "edited",
        "issue": {"number": number},
        "changes": {"body": {"from": before}},
        "sender": {"login": sender},
    }


def other_event(number: int) -> dict:
    return {"action": "edited", "issue": {"number": number}, "sender": {"login": "carol"}}


# --- persistence --------------------------------------------------------------------------------


async def test_event_notice_persists_until_the_template_key_is_restored():
    repo = Repo()
    repo.add(5, body=TEMPLATE, labels=("spec",))
    await run(repo, "issues", other_event(5))  # first run writes the block
    body = repo.issues[5]["body"]
    await run(repo, "issues", spec_edit(repo, 5, body.replace("- [ ] AC1: works\n", "")))
    assert open_rules(repo, 5) == ["V05"] and "v05-" in repo.guide(5)
    await run(repo, "issues", other_event(5))  # an unrelated event: the notice is still there
    assert open_rules(repo, 5) == ["V05"] and "v05-" in repo.guide(5).split("Resolved notices")[0]
    repo.issues[5]["body"] = body  # restored
    await run(repo, "issues", other_event(5))
    assert open_rules(repo, 5) == [] and "Resolved notices (1)" in repo.guide(5)
    assert [n["resolved"] for n in data(repo, 5)["notices"]] == ["restored"]


async def test_hand_set_label_notice_resolves_once_healed():
    repo = Repo()
    repo.add(7, labels=("enhancement", "phase:done"))
    event = {"action": "labeled", "issue": {"number": 7}, "label": {"name": "phase:done"}, "sender": {"login": "bob"}}
    await run(repo, "issues", event)
    assert open_rules(repo, 7) == ["V02"]
    await run(repo, "issues", other_event(7))  # the label was removed by the first run
    assert open_rules(repo, 7) == [] and data(repo, 7)["notices"][0]["resolved"] == "restored"


async def test_invalid_declaration_resolves_with_a_later_accepted_one():
    repo = Repo()
    repo.add(5, body="## Definition of Ready\n- [ ] open item\n", labels=("spec",))
    repo.issues[5]["user"] = {"login": "alice"}
    await run(repo, "issue_comment", comment_event(5, "/oct review", login="alice"))
    assert open_rules(repo, 5) == ["V07"]
    await run(repo, "issues", other_event(5))
    assert open_rules(repo, 5) == ["V07"]
    repo.issues[5]["body"] = DOR_DONE
    await run(repo, "issue_comment", comment_event(5, "/oct review", login="alice", comment_id=78))
    assert open_rules(repo, 5) == [] and data(repo, 5)["notices"][0]["resolved"] == "accepted"


async def test_closing_in_verification_resolves_when_reopened():
    repo = Repo()
    repo.add(5, labels=("spec", "wait:hardware-test"), state="closed", body=DOR_DONE)
    repo.issue_events[5] = [{"event": "closed", "commit_id": None}]
    closed = {"action": "closed", "issue": {"number": 5, "state_reason": "completed"}, "sender": {"login": "bob"}}
    await run(repo, "issues", closed)
    assert open_rules(repo, 5) == ["V08"]
    repo.issues[5]["state"] = "open"
    await run(repo, "issues", {"action": "reopened", "issue": {"number": 5}, "sender": {"login": "bob"}})
    assert open_rules(repo, 5) == [] and data(repo, 5)["notices"][0]["resolved"] == "reopened"


async def test_override_resolves_persisted_notices_even_before_activation():
    repo = Repo()
    repo.add(5, body=TEMPLATE, labels=("spec",))
    inactive = replace(ACTIVE, strikes_enabled_from=None)
    await run(repo, "issues", other_event(5), cfg=inactive)
    body = repo.issues[5]["body"]
    await run(repo, "issues", spec_edit(repo, 5, body.replace("- [ ] AC1: works\n", "")), cfg=inactive)
    assert open_rules(repo, 5) == ["V05"]
    await run(
        repo,
        "issue_comment",
        comment_event(5, "/oct override template changed on purpose", login="carol"),
        cfg=inactive,
    )
    assert open_rules(repo, 5) == [] and data(repo, 5)["notices"][0]["resolved"] == "overridden"
    assert repo.ledger() == []  # strikes are not active: nothing recorded


async def test_notices_age_out_after_the_window():
    repo = Repo()
    repo.add(5, body=TEMPLATE, labels=("spec",))
    await run(repo, "issues", other_event(5))
    body = repo.issues[5]["body"]
    await run(repo, "issues", spec_edit(repo, 5, body.replace("- [ ] AC1: works\n", "")))
    await run_at(repo, "issues", other_event(5), NOW + timedelta(days=59))
    assert open_rules(repo, 5) == ["V05"]
    await run_at(repo, "issues", other_event(5), NOW + timedelta(days=61))
    assert data(repo, 5).get("notices", []) == [] and "v05-" not in repo.guide(5)


async def test_audit_keeps_persisted_notices():
    from oct_status.main import run_audit

    repo = Repo()
    repo.add(5, body=TEMPLATE, labels=("spec",))
    await run(repo, "issues", other_event(5))
    body = repo.issues[5]["body"]
    await run(repo, "issues", spec_edit(repo, 5, body.replace("- [ ] AC1: works\n", "")))
    api = api_for(repo)
    await run_audit(api, ACTIVE, dry_run=False)
    await api.aclose()
    assert open_rules(repo, 5) == ["V05"]


async def test_unreadable_comments_never_wipe_persisted_notices(monkeypatch, tmp_path):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = Repo()
    repo.add(5, body=TEMPLATE, labels=("spec",))
    await run(repo, "issues", other_event(5))
    body = repo.issues[5]["body"]
    await run(repo, "issues", spec_edit(repo, 5, body.replace("- [ ] AC1: works\n", "")))
    before = repo.guide(5)
    original = repo.handler

    def failing(request):
        import httpx

        if request.url.path.endswith("/issues/5/comments") and request.method == "GET":
            return httpx.Response(500, json={})
        return original(request)

    repo.handler = failing  # type: ignore[method-assign]
    await run(repo, "issues", other_event(5))
    assert repo.guide(5) == before
    assert "comments of #5 unreadable" in summary.read_text(encoding="utf-8")


# --- level 3 ------------------------------------------------------------------------------------


async def test_level3_violation_reverts_issue_change_and_fails_pr_check():
    repo = Repo()
    seed(repo, "bob", [(1, "V02"), (2, "V02")])
    repo.add(7, labels=("enhancement", "phase:done"))
    event = {"action": "labeled", "issue": {"number": 7}, "label": {"name": "phase:done"}, "sender": {"login": "bob"}}
    await run(repo, "issues", event)
    assert "phase:done" not in repo.label_names(7)
    guide = repo.guide(7)
    assert "v02-" in guide and "reverted" in guide and "oct-status fails" not in guide

    repo.add_pr(10, body="Part of #5")
    repo.add(5, labels=("bug",))  # implemented by the PR; no spec readiness involved
    await run(repo, "pull_request_target", pr_event(10, "opened"))
    assert await check(repo, 10) == 0
    repo.issues[10]["labels"].append({"name": "wait:ci"})
    labeled = pr_event(10, "labeled", sender="bob", label={"name": "wait:ci"})
    await run(repo, "pull_request_target", labeled)
    assert "oct-status fails" in repo.guide(10) and "wait:ci" not in repo.label_names(10)
    assert await check(repo, 10) == 1  # blocked although the label was healed in the same run
    await run(repo, "pull_request_target", pr_event(10, "synchronize"))  # the next event resolves it
    assert await check(repo, 10) == 0


async def test_level3_revert_also_when_the_label_history_is_unreadable():
    repo = Repo()
    repo.timeline_ok = False
    seed(repo, "bob", [(1, "V02"), (2, "V02")])
    repo.add(7, labels=("enhancement", "phase:done"))
    event = {"action": "labeled", "issue": {"number": 7}, "label": {"name": "phase:done"}, "sender": {"login": "bob"}}
    await run(repo, "issues", event)
    assert "phase:done" not in repo.label_names(7) and "reverted" in repo.guide(7)
    # Below level 3 an unreadable history keeps the phase label untouched (fail closed).
    repo.add(8, labels=("enhancement", "phase:done"))
    event8 = {"action": "labeled", "issue": {"number": 8}, "label": {"name": "phase:done"}, "sender": {"login": "eve"}}
    await run(repo, "issues", event8)
    assert "phase:done" in repo.label_names(8)


async def test_level3_removed_label_is_restored_on_an_issue():
    repo = Repo()
    seed(repo, "bob", [(1, "V02"), (2, "V02")])
    repo.add(7, labels=("enhancement",))
    await run(repo, "issues", other_event(7))
    assert "phase:new" in repo.label_names(7)
    repo.issues[7]["labels"] = [lb for lb in repo.issues[7]["labels"] if lb["name"] != "phase:new"]
    event = {"action": "unlabeled", "issue": {"number": 7}, "label": {"name": "phase:new"}, "sender": {"login": "bob"}}
    await run(repo, "issues", event)
    assert "phase:new" in repo.label_names(7) and "reverted" in repo.guide(7)


# --- level 3: V08 reopens the issue ----------------------------------------------------------------

REOPEN = {"state": "open", "state_reason": "reopened"}


def closed_event(number: int = 5, sender: str = "bob") -> dict:
    return {"action": "closed", "issue": {"number": number, "state_reason": "completed"}, "sender": {"login": sender}}


def verification_issue(repo: Repo, number: int = 5) -> dict:
    repo.add(number, labels=("spec", "wait:hardware-test"), state="closed", body=DOR_DONE)
    repo.issue_events[number] = [{"event": "closed", "commit_id": None}]
    return closed_event(number)


def reopen_patches(repo: Repo) -> list[int]:
    return [n for n, body in repo.patches if body == REOPEN]


async def test_level3_v08_reopens_the_issue_and_records_the_revert():
    repo = Repo()
    seed(repo, "bob", [(1, "V08"), (2, "V08")])
    event = verification_issue(repo)
    await run(repo, "issues", event)
    assert repo.issues[5]["state"] == "open" and reopen_patches(repo) == [5]
    guide = repo.guide(5)
    assert "Reverted: the issue was reopened because it was closed without hardware verification" in guide
    assert "verify on a device or use `/oct verified`, then close again" in guide
    assert open_rules(repo, 5) == ["V08"]  # the reopening does not resolve the notice
    assert "wait:hardware-test" in repo.label_names(5)
    await run(repo, "issues", other_event(5))  # a later unrelated event keeps it open
    assert open_rules(repo, 5) == ["V08"] and repo.issues[5]["state"] == "open"


async def test_v08_below_level3_does_not_reopen():
    repo = Repo()
    seed(repo, "bob", [(1, "V08")])  # this one is the second strike: level 2
    await run(repo, "issues", verification_issue(repo))
    assert repo.issues[5]["state"] == "closed" and reopen_patches(repo) == []
    assert "Reverted" not in repo.guide(5) and open_rules(repo, 5) == ["V08"]


async def test_v08_before_strikes_are_active_does_not_reopen():
    repo = Repo()
    inactive = replace(ACTIVE, strikes_enabled_from=None)
    await run(repo, "issues", verification_issue(repo), cfg=inactive)
    assert reopen_patches(repo) == [] and repo.issues[5]["state"] == "closed"


async def test_own_reopen_is_ignored_and_a_second_close_counts_once():
    repo = Repo()
    seed(repo, "bob", [(1, "V08"), (2, "V08")])
    event = verification_issue(repo)
    await run(repo, "issues", event)
    entries = len(repo.ledger())
    patches = len(repo.patches)
    # The reopening by the bot raises issues.reopened: ignored, nothing is written.
    await run(repo, "issues", {"action": "reopened", "issue": {"number": 5}, "sender": {"login": "oct-support"}})
    assert len(repo.patches) == patches and len(repo.ledger()) == entries
    # A person closes it again: V08 again, the pair (artifact, rule) is not counted twice, reopened again.
    repo.issues[5]["state"] = "closed"
    await run(repo, "issues", event)
    assert len(repo.ledger()) == entries and reopen_patches(repo) == [5, 5]
    assert [n["rule"] for n in data(repo, 5)["notices"]] == ["V08"]
    assert open_rules(repo, 5) == ["V08"]


async def test_level3_v08_resolves_when_verified():
    repo = Repo()
    seed(repo, "bob", [(1, "V08"), (2, "V08")])
    await run(repo, "issues", verification_issue(repo))
    await run(repo, "issue_comment", comment_event(5, "/oct verified Bose ST10", login="carol"))
    assert open_rules(repo, 5) == [] and data(repo, 5)["notices"][0]["resolved"] == "verified"


async def test_level3_v08_resolves_when_overridden_and_is_not_reverted_again():
    repo = Repo()
    seed(repo, "bob", [(1, "V08"), (2, "V08")])
    event = verification_issue(repo)
    await run(repo, "issues", event)
    await run(repo, "issue_comment", comment_event(5, "/oct override verified out of band", login="carol"))
    assert open_rules(repo, 5) == [] and data(repo, 5)["notices"][0]["resolved"] == "overridden"
    repo.issues[5]["state"] = "closed"
    await run(repo, "issues", event)
    assert reopen_patches(repo) == [5] and repo.issues[5]["state"] == "closed"


async def test_level3_v08_dry_run_writes_nothing():
    repo = Repo()
    seed(repo, "bob", [(1, "V08"), (2, "V08")])
    await run(repo, "issues", verification_issue(repo), dry_run=True)
    assert repo.patches == [] and repo.issues[5]["state"] == "closed"


async def test_level3_v08_read_only_api_never_reaches_the_patch():
    from oct_status.api import GitHubApi

    repo = Repo()
    seed(repo, "bob", [(1, "V08"), (2, "V08")])
    event = verification_issue(repo)
    transport = httpx.MockTransport(repo.handler)
    api = GitHubApi("t", "o/r", transport, sleep=_nosleep, read_only=True)
    await run_event(api, ACTIVE, "issues", event, dry_run=True, clock=lambda: NOW)
    await api.aclose()
    assert repo.patches == [] and repo.issues[5]["state"] == "closed"


async def test_level3_v08_with_an_unreadable_ledger_does_not_reopen():
    repo = Repo()
    seed(repo, "bob", [(1, "V08"), (2, "V08")])
    repo.fail_ledger_read = True
    await run(repo, "issues", verification_issue(repo))
    assert reopen_patches(repo) == [] and repo.issues[5]["state"] == "closed"


async def test_level3_v08_with_an_unreadable_guide_does_not_reopen():
    repo = Repo()
    seed(repo, "bob", [(1, "V08"), (2, "V08")])
    event = verification_issue(repo)
    original = repo.handler

    def failing(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issues/5/comments"):
            return httpx.Response(500, json={})
        return original(request)

    repo.handler = failing  # type: ignore[method-assign]
    await run(repo, "issues", event)
    assert reopen_patches(repo) == [] and repo.issues[5]["state"] == "closed"


async def test_level3_v08_with_a_corrupt_guide_does_not_reopen():
    repo = Repo()
    seed(repo, "bob", [(1, "V08"), (2, "V08")])
    event = verification_issue(repo)
    repo.comments[5] = [{"id": 9, "body": f"{MARKER}\nno data", "user": {"login": "oct-support"}}]
    await run(repo, "issues", event)
    assert reopen_patches(repo) == [] and repo.issues[5]["state"] == "closed"


# --- data shape ---------------------------------------------------------------------------------


def _body(payload) -> str:
    text = payload if isinstance(payload, str) else json.dumps(payload).replace("--", "\\u002d\\u002d")
    return f"{MARKER}\n<!-- oct-next-data {text} -->\n"


GOOD = {
    "rule": "V02",
    "user": "bob",
    "artifact": 7,
    "ts": NOW.isoformat(),
    "level": 1,
    "hint": "h",
    "key": "phase:done",
    "resolved": "",
}


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD, "rule": "V99"},
        {**GOOD, "user": "bad user"},
        {**GOOD, "artifact": 0},
        {**GOOD, "artifact": True},
        {**GOOD, "ts": "yesterday"},
        {**GOOD, "ts": "2026-11-01T00:00:00"},  # no time zone
        {**GOOD, "level": 0},
        {**GOOD, "level": "3"},
        {**GOOD, "hint": 5},
        {**GOOD, "resolved": "because I said so"},
        "not an object",
    ],
)
def test_malformed_records_are_dropped(bad):
    state = parse_state(_body({"notices": [GOOD, bad]}))
    assert len(state.records) == 1 and state.records[0].rule == "V02"


def test_data_is_validated_and_scrubbed():
    # A missing, oversized or structurally invalid data block is unknown (None), never empty.
    assert parse_state("no guide") is None
    assert parse_state(_body("{not json")) is None
    assert parse_state(_body([1, 2])) is None
    assert parse_state(_body({"notices": "x"})) is None
    assert parse_state(_body({"notices": [GOOD] * 5, "pad": "x" * 70_000})) is None
    empty = parse_state(_body({"paths_accepted": {"sha": "nope"}, "paths_pending": {"sha": "x"}}))
    assert empty is not None and empty.accepted is None and empty.pending == "" and empty.records == ()
    hostile = {**GOOD, "hint": "<!-- --> @gitar-bot\x00 & go", "key": "<b>x</b>"}
    rec = parse_state(_body({"notices": [hostile]})).records[0]
    assert "<" not in rec.hint and ">" not in rec.hint and "\x00" not in rec.hint and "gitar-bot" not in rec.hint
    assert "<" not in rec.key
    many = {"notices": [{**GOOD, "artifact": n} for n in range(1, 200)]}
    assert len(parse_state(_body(many)).records) <= 2 * MAX_OPEN


def test_forged_record_cannot_mention_link_or_embed():
    forged = {**GOOD, "hint": "ping @alice ![x](https://evil.example/p.png) [click](https://evil.example)"}
    rec = parse_state(_body({"notices": [forged]})).records[0]
    text = "\n".join(render([rec], is_pr=False))
    assert "@alice" not in text and "](" not in text.replace(f"]({WORKFLOW}", "") and "![" not in text
    assert scrub(rec.hint) == rec.hint  # idempotent


def test_written_data_keeps_a_size_budget_and_level3_notices(monkeypatch):
    from oct_status import notices

    monkeypatch.setattr(notices, "DATA_BUDGET", 6_000)
    long = "x" * 290
    old_open = [replace(_rec("V05", key=f"i:{n}{long}"), ts=NOW - timedelta(hours=n + 1)) for n in range(20)]
    resolved = [
        replace(_rec("V07", key="review", resolved="accepted"), ts=NOW - timedelta(minutes=n)) for n in range(10)
    ]
    blocking = replace(_rec("V02", key="wait:ci", level=4), ts=NOW - timedelta(days=30), hint="é" * 280)
    budget_cut = state_data([*old_open, *resolved, blocking], None)
    kept = budget_cut["notices"]
    assert len(json.dumps(kept, ensure_ascii=False)) <= notices.DATA_BUDGET < DATA_BUDGET
    assert not [n for n in kept if n["resolved"]]  # resolved ones go first
    assert any(n["level"] == 4 for n in kept)  # level 3+ is never dropped
    # The newest open notices survive; the oldest low-level ones were dropped.
    assert len(kept) < 21 and kept[-1]["key"].startswith("i:0")
    # Non-ASCII text is written as is (no \\u escapes inflating the comment).
    assert "é" in render_guide_data(blocking)


def render_guide_data(rec: Record) -> str:
    from oct_status.guide import render_guide
    from oct_status.model import Derived, Phase

    from .conftest import make_snapshot

    return render_guide(
        make_snapshot(), Derived(Phase.NEW, frozenset(), None), [], [], [], data=state_data([rec], None)
    )


def test_state_data_round_trip_is_stable():
    rec = Record("V05", "bob", 5, NOW, 2, "Removed: x & y.", "i:ac1", "")
    first = state_data([rec], None)
    text = json.dumps(first)
    again = state_data(list(parse_state(_body(text)).records), None)
    assert again == first


# --- resolution rules (pure) --------------------------------------------------------------------


def _rec(rule: str, key: str = "", resolved: str = "", level: int = 1, days: int = 0) -> Record:
    return Record(rule, "bob", 10, NOW - timedelta(days=days), level, "hint", key, resolved)


def _update(records, snap, derived, found=(), accepted=None):
    from oct_status.model import Graph
    from oct_status.notices import update

    graph = Graph([], {snap.number: snap}, {})
    return update(records, list(found), snap, derived, graph, ACTIVE, NOW, accepted)


def test_resolution_rules_without_an_event():
    from oct_status.model import Derived, Phase, Wait
    from oct_status.render import render_block

    from .conftest import make_snapshot

    pr = make_snapshot(number=10, is_pr=True, title="feat: x", author="alice")
    in_review = Derived(Phase.IN_REVIEW, frozenset({Wait.MAINTAINER}), None)
    # V01 holds while the PR has no spec reference, and is fixed once it has one.
    assert _update([_rec("V01")], pr, in_review)[0].resolved == ""
    assert _update([_rec("V01")], replace(pr, title="docs: x"), in_review)[0].resolved == "fixed"
    # V03: restored once the body carries an intact block again.
    assert _update([_rec("V03")], pr, in_review)[0].resolved == ""
    from oct_status.model import Graph

    block = render_block(pr, in_review, Graph([], {10: pr}, {}), ACTIVE)
    assert _update([_rec("V03")], replace(pr, body=block or ""), in_review)[0].resolved == "restored"
    # V08: verified once the artifact is no longer in verification.
    closed = make_snapshot(number=10, state="closed", labels=frozenset({"spec"}))
    assert _update([_rec("V08")], closed, Derived(Phase.VERIFICATION, frozenset(), None))[0].resolved == ""
    assert _update([_rec("V08")], closed, Derived(Phase.DONE, frozenset(), None))[0].resolved == "verified"


def test_redetection_updates_or_reopens_records():
    from oct_status.model import Derived, Phase

    from .conftest import make_snapshot

    pr = make_snapshot(number=10, is_pr=True, title="feat: x", author="alice")
    derived = Derived(Phase.IN_REVIEW, frozenset(), None)
    state = _rec("V01", days=3)
    again = replace(_rec("V01", level=3), hint="new")
    kept = _update([state], pr, derived, [again])[0]
    assert (kept.ts, kept.level, kept.resolved) == (state.ts, 3, "")  # a state keeps its first date
    healed = _rec("V02", key="wait:ci", resolved="restored", days=2)
    reopened = _update([healed], pr, derived, [_rec("V02", key="wait:ci")])[0]
    assert reopened.resolved == "" and reopened.ts == NOW  # an event violation counts from the new event
    covered = _update([_rec("V01", resolved="overridden", days=5)], pr, derived, [_rec("V01")])[0]
    assert covered.resolved == "overridden"  # an override keeps covering the persisting state
    expired = _update([_rec("V05", key="i:x", days=61), _rec("V02", resolved="restored", days=70)], pr, derived)
    assert expired == []


def test_resolved_records_are_capped():
    from oct_status.model import Derived, Phase
    from oct_status.notices import MAX_RESOLVED

    from .conftest import make_snapshot

    snap = make_snapshot(number=10)
    many = [replace(_rec("V07", key="review", resolved="accepted"), ts=NOW - timedelta(minutes=n)) for n in range(30)]
    out = _update(many, snap, Derived(Phase.NEW, frozenset(), None))
    assert len(out) == MAX_RESOLVED and min(r.ts for r in out) == NOW - timedelta(minutes=MAX_RESOLVED - 1)


async def test_check_fails_closed_when_the_guide_is_unreadable():
    repo = Repo()
    repo.add_pr(10, body="Part of #5")
    repo.add(5, labels=("bug",))
    await run(repo, "pull_request_target", pr_event(10, "opened"))
    assert await check(repo, 10) == 0
    original = repo.handler

    def failing(request):
        import httpx

        if request.url.path.endswith("/issues/10/comments") and request.method == "GET":
            return httpx.Response(500, json={})
        return original(request)

    repo.handler = failing  # type: ignore[method-assign]
    assert await check(repo, 10) == 1


async def test_invalid_guide_data_is_unknown_and_never_overwritten(monkeypatch, tmp_path):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = Repo()
    repo.add(5, body=TEMPLATE, labels=("spec",))
    await run(repo, "issues", other_event(5))
    guide = next(c for c in repo.comments[5] if MARKER in c["body"])
    guide["body"] = guide["body"].split("<!-- oct-next-data")[0] + "<!-- oct-next-data {broken -->\n"
    before = guide["body"]
    await run(repo, "issues", other_event(5))
    assert guide["body"] == before
    assert "guide data of #5 is missing, oversized or invalid" in summary.read_text(encoding="utf-8")


def test_cap_never_drops_open_level3_notices():
    from oct_status.notices import _cap

    severe = [replace(_rec("V02", key=f"wait:{n}", level=3), ts=NOW - timedelta(days=50, minutes=n)) for n in range(25)]
    light = [replace(_rec("V05", key=f"i:{n}"), ts=NOW - timedelta(minutes=n)) for n in range(10)]
    kept = _cap([*light, *severe])
    assert sum(r.level >= 3 for r in kept) == 25 and not [r for r in kept if r.level < 3]
    assert len(_cap([*light, *severe[:5]])) == 15  # everything fits: nothing dropped


def test_budget_is_measured_on_the_encoded_payload(monkeypatch):
    from oct_status import notices

    monkeypatch.setattr(notices, "DATA_BUDGET", 3_000)
    dashes = [replace(_rec("V05", key=f"i:{n}"), hint="--" * 140, ts=NOW - timedelta(minutes=n)) for n in range(8)]
    kept = state_data(dashes, None)["notices"]
    # Raw JSON would fit more records; every "--" costs 12 characters once encoded.
    assert len(notices.encode(kept)) <= 3_000 and len(kept) < len(dashes)
    assert len(json.dumps([{**n} for n in state_data(dashes[:3], None)["notices"]])) < 3_000


async def test_too_large_guide_data_keeps_only_blocking_notices(monkeypatch, tmp_path):
    from oct_status import main as main_module

    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = Repo()
    seed(repo, "bob", [(1, "V02"), (2, "V02")])
    repo.add(5, body=TEMPLATE, labels=("spec",))
    await run(repo, "issues", other_event(5))
    body = repo.issues[5]["body"]
    await run(repo, "issues", spec_edit(repo, 5, body.replace("- [ ] AC1: works\n", ""), sender="eve"))
    repo.issues[5]["labels"].append({"name": "phase:done"})
    label = {"action": "labeled", "issue": {"number": 5}, "label": {"name": "phase:done"}, "sender": {"login": "bob"}}
    monkeypatch.setattr(main_module, "_fits", lambda text: '"V05"' not in text)  # the full data is "too large"
    await run(repo, "issues", label)
    assert open_rules(repo, 5) == ["V02"]  # the blocking notice survives, the light one was dropped
    monkeypatch.setattr(main_module, "_fits", lambda text: False)
    before = repo.guide(5)
    await run(repo, "issues", other_event(5))
    assert repo.guide(5) == before and "would be too large" in summary.read_text(encoding="utf-8")


async def test_invalid_guide_warning_names_the_recovery_and_its_cost(monkeypatch, tmp_path):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = Repo()
    repo.add(5, body=TEMPLATE, labels=("spec",))
    await run(repo, "issues", other_event(5))
    guide = next(c for c in repo.comments[5] if MARKER in c["body"])
    guide["body"] = guide["body"].split("<!-- oct-next-data")[0]
    await run(repo, "issues", other_event(5))
    text = summary.read_text(encoding="utf-8")
    assert "delete it to start over" in text and "wipes its persisted notices" in text


async def test_guide_changed_twice_during_a_run_is_not_rewritten(monkeypatch, tmp_path):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = Repo()
    repo.add(7, labels=("enhancement",))
    await run(repo, "issues", other_event(7))
    original = repo.handler
    count = {"n": 0}

    def churn(request):
        if request.url.path.endswith("/issues/7/comments") and request.method == "GET":
            count["n"] += 1
            if count["n"] >= 2:  # every later read sees another overlapping write
                guide = next(c for c in repo.comments[7] if MARKER in c["body"])
                guide["body"] += " "
        return original(request)

    repo.handler = churn  # type: ignore[method-assign]
    await run(repo, "issues", other_event(7))
    assert "changed twice during this run" in summary.read_text(encoding="utf-8")
