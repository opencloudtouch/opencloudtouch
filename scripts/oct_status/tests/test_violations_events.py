"""Event pipeline with violations: guide notices, ledger entries, ladder, dry-run and failure modes."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import httpx

from oct_status.main import run_event

from .test_commands import CommandRepo, comment_event
from .test_main_events import BOT, CFG, ROOT, api_for
from .test_rules import DOR_DONE

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
ACTIVE = replace(CFG, strikes_enabled_from=date(2026, 10, 1))
LEDGER = 99
ANCHOR = "docs/WORKFLOW.md#v01-"


def clock() -> datetime:
    return NOW


class Repo(CommandRepo):
    """CommandRepo with pull requests and a locked ledger issue."""

    def __init__(self, ledger: bool = True) -> None:
        super().__init__()
        self.prs: dict[int, dict] = {}
        self.fail_ledger_read = False
        self.issue_events: dict[int, list[dict]] = {}
        if ledger:
            self.add(LEDGER)
            self.issues[LEDGER].update(title="oct-status ledger", locked=True, user={"login": BOT})

    def add_pr(
        self,
        number: int,
        body: str = "",
        author: str = "alice",
        fork: bool = False,
        title: str = "feat: x",
        association: str = "CONTRIBUTOR",
    ) -> None:
        self.add(number, body=body)
        self.issues[number].update(title=title, user={"login": author})
        head_repo = "fork/r" if fork else "o/r"
        self.prs[number] = {
            "number": number,
            "title": title,
            "body": body,
            "state": "open",
            "merged": False,
            "draft": False,
            "user": {"login": author},
            "author_association": association,
            "labels": [],
            "base": {"ref": "main", "repo": {"full_name": "o/r"}},
            "head": {"ref": f"feat/{number}", "sha": f"{number:040x}", "repo": {"full_name": head_repo}},
        }

    def ledger(self) -> list[dict]:
        return [json.loads(c["body"]) for c in self.comments.get(LEDGER, [])]

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if m := re.fullmatch(rf"{ROOT}/pulls/(\d+)", path):
            if int(m[1]) in self.prs:
                pr = {**self.prs[int(m[1])], "body": self.issues[int(m[1])]["body"]}
                pr["labels"] = self.issues[int(m[1])]["labels"]
                return httpx.Response(200, json=pr)
            return httpx.Response(404, json={})
        if re.fullmatch(rf"{ROOT}/pulls/\d+/(reviews|commits)", path):
            return httpx.Response(200, json=[])
        if re.fullmatch(rf"{ROOT}/commits/[0-9a-f]+/check-runs", path):
            return httpx.Response(200, json={"check_runs": []})
        if m := re.fullmatch(rf"{ROOT}/issues/(\d+)/events", path):
            if int(m[1]) in self.issue_events:
                return httpx.Response(200, json=self.issue_events[int(m[1])])
            return httpx.Response(404, json={})
        if path == f"{ROOT}/issues/{LEDGER}/comments" and request.method == "GET" and self.fail_ledger_read:
            return httpx.Response(500, json={})
        if path == "/repos/o/r/graphql" or path == "/graphql":
            return httpx.Response(200, json={"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": []}}}}})
        return super().handler(request)


def pr_event(
    number: int, action: str = "opened", sender: str = "alice", association: str = "CONTRIBUTOR", **extra
) -> dict:
    pull = {"number": number, "author_association": association}
    return {"action": action, "pull_request": pull, "sender": {"login": sender}, **extra}


def seed(repo: Repo, user: str, pairs: list[tuple[int, str]]) -> None:
    for artifact, rule in pairs:
        body = {"v": 1, "kind": "violation", "user": user, "artifact": artifact, "rule": rule, "ts": NOW.isoformat()}
        repo.comments.setdefault(LEDGER, []).append(
            {"id": 5000 + len(repo.comments.get(LEDGER, [])), "body": json.dumps(body), "user": {"login": BOT}}
        )


async def run(repo: Repo, event: str, payload: dict, cfg=ACTIVE, dry_run: bool = False) -> None:
    api = api_for(repo)
    assert await run_event(api, cfg, event, payload, dry_run=dry_run, clock=clock) == 0
    await api.aclose()


def v01_notices(repo: Repo, number: int) -> int:
    return repo.guide(number).count(ANCHOR)


async def test_event_with_violation_writes_notice_to_guide():
    repo = Repo()
    repo.add_pr(10)
    await run(repo, "pull_request_target", pr_event(10))
    guide = repo.guide(10)
    assert v01_notices(repo, 10) == 1 and "/oct no-spec" in guide
    assert "/oct override" not in guide  # level 1
    assert [(e["rule"], e["user"], e["artifact"]) for e in repo.ledger()] == [("V01", "alice", 10)]
    # A repeated event adds nothing: no new ledger entry and an identical guide.
    before, writes = repo.guide(10), len(repo.writes)
    await run(repo, "pull_request_target", pr_event(10, "synchronize"))
    assert repo.guide(10) == before and v01_notices(repo, 10) == 1
    assert len(repo.ledger()) == 1
    assert not [w for w in repo.writes[writes:] if w[1].endswith(f"/issues/{LEDGER}/comments")]


async def test_ladder_escalates_in_the_guide():
    repo = Repo()
    repo.add_pr(10)
    seed(repo, "alice", [(1, "V01")])
    await run(repo, "pull_request_target", pr_event(10))
    assert "/oct override" in repo.guide(10) and "fails" not in repo.guide(10)  # second strike
    repo.add_pr(11)
    seed(repo, "alice", [(2, "V01")])
    await run(repo, "pull_request_target", pr_event(11))
    assert "oct-status fails" in repo.guide(11)  # fourth: three pairs plus this one


async def test_no_strikes_before_activation_date():
    repo = Repo(ledger=False)  # not even the ledger issue is needed
    repo.add_pr(10)
    repo.add(LEDGER)
    repo.issues[LEDGER].update(title="oct-status ledger", locked=True, user={"login": BOT})
    seed(repo, "alice", [(1, "V01"), (2, "V01"), (3, "V01")])
    future = replace(CFG, strikes_enabled_from=date(2027, 1, 1))
    await run(repo, "pull_request_target", pr_event(10), cfg=future)
    guide = repo.guide(10)
    assert v01_notices(repo, 10) == 1 and "/oct override" not in guide and "fails" not in guide
    assert len(repo.ledger()) == 3  # nothing recorded
    await run(repo, "pull_request_target", pr_event(10), cfg=CFG)  # no date set: strikes are off
    assert "fails" not in repo.guide(10) and len(repo.ledger()) == 3


async def test_dry_run_reports_but_writes_nothing():
    repo = Repo()
    repo.add_pr(10)
    await run(repo, "pull_request_target", pr_event(10), dry_run=True)
    assert repo.ledger() == [] and repo.guide(10) == ""
    assert not repo.writes


async def test_ledger_unreadable_does_not_escalate(monkeypatch, tmp_path):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = Repo()
    repo.add_pr(10)
    seed(repo, "alice", [(1, "V01"), (2, "V01"), (3, "V01")])
    repo.fail_ledger_read = True
    await run(repo, "pull_request_target", pr_event(10))
    guide = repo.guide(10)
    assert v01_notices(repo, 10) == 1 and "/oct override" not in guide and "fails" not in guide
    assert "ledger unavailable" in summary.read_text(encoding="utf-8")
    assert len(repo.ledger()) == 3


async def test_exempt_authors_get_no_notice_and_no_entry():
    repo = Repo()
    repo.add_pr(10, author=BOT)
    await run(repo, "pull_request_target", pr_event(10, sender=BOT))
    repo.add_pr(11, fork=True, author="newbie", association="FIRST_TIME_CONTRIBUTOR")
    await run(repo, "pull_request_target", pr_event(11, sender="newbie"))
    repo.add_pr(12, author="dependabot[bot]")
    await run(repo, "pull_request_target", pr_event(12, sender="dependabot[bot]"))
    assert all(ANCHOR not in repo.guide(n) for n in (10, 11, 12)) and repo.ledger() == []


async def test_no_spec_waives_v01():
    repo = Repo()
    repo.add_pr(10, author="alice")
    repo.comments[10] = [{"id": 1, "body": "/oct no-spec typo fix", "user": {"login": "alice"}}]
    await run(repo, "pull_request_target", pr_event(10))
    assert ANCHOR not in repo.guide(10) and repo.ledger() == []


async def test_hand_set_fact_label_is_a_violation_and_not_trusted():
    repo = Repo()
    repo.add(7, labels=("enhancement", "phase:done"))
    event = {"action": "labeled", "issue": {"number": 7}, "label": {"name": "phase:done"}, "sender": {"login": "bob"}}
    await run(repo, "issues", event)
    assert "v02-" in repo.guide(7) and [(e["rule"], e["user"]) for e in repo.ledger()] == [("V02", "bob")]
    assert "phase:done" not in repo.label_names(7) and "phase:new" in repo.label_names(7)


async def test_labels_written_by_the_bot_are_not_violations():
    repo = Repo()
    repo.add(7, labels=("enhancement",))
    event = {
        "action": "labeled",
        "issue": {"number": 7},
        "label": {"name": "phase:done"},
        "sender": {"login": "github-actions[bot]"},
    }
    await run(repo, "issues", event)
    assert "v02-" not in repo.guide(7) and repo.ledger() == []


async def test_invalid_declaration_is_v07():
    repo = Repo()
    repo.add(5, body="## Definition of Ready\n- [ ] open item\n", labels=("spec",))
    repo.issues[5]["user"] = {"login": "alice"}
    await run(repo, "issue_comment", comment_event(5, "/oct review", login="alice"))
    guide = repo.guide(5)
    assert "was rejected" in guide and "v07-" in guide
    assert [(e["rule"], e["user"]) for e in repo.ledger()] == [("V07", "alice")]
    # A command that is not a declaration, or an accepted one, is no violation.
    repo.add(6, body=DOR_DONE, labels=("spec",))
    repo.issues[6]["user"] = {"login": "alice"}
    await run(repo, "issue_comment", comment_event(6, "/oct review", login="alice"))
    assert "v07-" not in repo.guide(6)


async def test_override_resolves_the_notice_and_is_not_counted():
    repo = Repo()
    repo.add_pr(10)
    await run(repo, "pull_request_target", pr_event(10))
    assert len(repo.ledger()) == 1
    await run(repo, "issue_comment", comment_event(10, "/oct override false alarm", login="carol"))
    kinds = [e["kind"] for e in repo.ledger()]
    assert kinds == ["violation", "override"]
    guide = repo.guide(10)
    assert "recorded and effective" in guide
    assert "Resolved notices (1)" in guide and "overridden by a maintainer" in guide
    assert len(repo.ledger()) == 2  # the overridden pair is not recorded again


async def test_override_in_dry_run_is_only_reported():
    repo = Repo()
    repo.add_pr(10)
    await run(repo, "issue_comment", comment_event(10, "/oct override why", login="carol"), dry_run=True)
    assert repo.ledger() == [] and not repo.writes


async def test_override_fails_closed_when_ledger_missing():
    repo = Repo(ledger=False)
    repo.add_pr(10)
    api = api_for(repo)
    await run_event(
        api, ACTIVE, "issue_comment", comment_event(10, "/oct override why", login="carol"), dry_run=False, clock=clock
    )
    await api.aclose()
    assert "could not be recorded" in repo.guide(10)
    assert (77, "-1") in repo.reactions


async def test_first_time_fork_author_is_exempt_for_an_event_without_association():
    """A check_suite payload carries no author_association: the snapshot's value decides."""
    repo = Repo()
    repo.add_pr(11, fork=True, author="newbie", association="FIRST_TIME_CONTRIBUTOR")
    sha = f"{11:040x}"
    payload = {"action": "completed", "check_suite": {"pull_requests": [{"number": 11}], "head_sha": sha}}
    await run(repo, "check_suite", payload)
    assert ANCHOR not in repo.guide(11) and repo.ledger() == []
    repo.add_pr(12, fork=True, author="regular", association="CONTRIBUTOR")
    # A forged claim in the payload does not help.
    payload = {
        "action": "completed",
        "check_suite": {
            "pull_requests": [{"number": 12, "author_association": "FIRST_TIMER"}],
            "head_sha": f"{12:040x}",
        },
    }
    await run(repo, "check_suite", payload)
    assert v01_notices(repo, 12) == 1


async def test_non_precondition_rejections_are_not_v07():
    repo = Repo()
    repo.add(5, body="## Definition of Ready\n- [x] done\n", labels=("spec",))
    repo.issues[5]["user"] = {"login": "alice"}
    await run(repo, "issue_comment", comment_event(5, "/oct ready", login="carol"))  # syntax error
    await run(
        repo, "issue_comment", comment_event(5, "/oct rework", login="carol")
    )  # missing reason is not a declaration
    await run(repo, "issue_comment", comment_event(5, "/oct review", login="bob"))  # not the author
    assert repo.ledger() == []
    await run(
        repo, "issue_comment", comment_event(5, "/oct ready --reviewer alice", login="carol")
    )  # reviewer is author
    assert [(e["rule"], e["user"]) for e in repo.ledger()] == [("V07", "carol")]


async def test_missing_ledger_issue_does_not_escalate_in_write_mode(monkeypatch, tmp_path):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = Repo(ledger=False)  # the ledger issue cannot be created either (no POST /issues in the fake)
    repo.add_pr(10)
    await run(repo, "pull_request_target", pr_event(10))
    guide = repo.guide(10)
    assert v01_notices(repo, 10) == 1 and "/oct override" not in guide and "fails" not in guide
    assert "ledger unavailable" in summary.read_text(encoding="utf-8")


async def test_ledger_posts_never_mention_accounts():
    repo = Repo()
    repo.add_pr(10)
    await run(repo, "pull_request_target", pr_event(10))
    await run(repo, "issue_comment", comment_event(10, "/oct override @gitar-bot and @someone please", login="carol"))
    bodies = [c["body"] for c in repo.comments[LEDGER]]
    assert len(bodies) == 2 and all("@" not in b and "gitar-bot" not in b.lower() for b in bodies)
    assert all(isinstance(json.loads(b), dict) for b in bodies)  # still valid JSON


def _verification_issue(repo: Repo) -> dict:
    repo.add(5, labels=("spec", "wait:hardware-test"), state="closed", body="## Definition of Ready\n- [x] done\n")
    return {
        "action": "closed",
        "issue": {"number": 5, "state_reason": "completed"},
        "sender": {"login": "bob"},
    }


async def test_v08_charged_only_when_not_closed_by_a_merged_change():
    repo = Repo()
    event = _verification_issue(repo)
    repo.issue_events[5] = [{"event": "closed", "commit_id": None}]
    await run(repo, "issues", event)
    assert [(e["rule"], e["user"]) for e in repo.ledger()] == [("V08", "bob")]


async def test_v08_not_charged_for_close_by_merge_unknown_closer_or_not_planned():
    repo = Repo()
    event = _verification_issue(repo)
    repo.issue_events[5] = [{"event": "closed", "commit_id": None}, {"event": "closed", "commit_id": "abc123"}]
    await run(repo, "issues", event)  # closed by the merge of a pull request
    del repo.issue_events[5]
    await run(repo, "issues", event)  # timeline unreadable: fail closed
    repo.issue_events[5] = [{"event": "closed", "commit_id": None}]
    event["issue"]["state_reason"] = "not_planned"
    await run(repo, "issues", event)
    assert repo.ledger() == []


async def test_unreadable_label_history_is_reported(monkeypatch, tmp_path):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = Repo()
    repo.add(7, labels=("enhancement", "phase:done"))
    await run(repo, "issues", {"action": "opened", "issue": {"number": 7}, "sender": {"login": "bob"}})
    assert "label history of #7 unreadable" in summary.read_text(encoding="utf-8")
    assert "phase:done" not in repo.label_names(7)


async def test_override_keeps_a_persisting_violation_resolved_after_renewal():
    repo = Repo()
    repo.add_pr(10)
    await run(repo, "pull_request_target", pr_event(10))
    await run(repo, "issue_comment", comment_event(10, "/oct override known", login="carol"))
    entries = repo.ledger()
    assert entries[1]["covers"] == ["V01"]
    late = NOW + timedelta(days=55)
    api = api_for(repo)
    await run_event(api, ACTIVE, "pull_request_target", pr_event(10, "synchronize"), dry_run=False, clock=lambda: late)
    await api.aclose()
    assert [e["kind"] for e in repo.ledger()] == ["violation", "override", "override"]
    assert "Resolved notices (1)" in repo.guide(10)
