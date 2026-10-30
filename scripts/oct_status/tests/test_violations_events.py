"""Event pipeline with violations: guide notices, ledger entries, ladder, dry-run and failure modes."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import UTC, date, datetime

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
        if ledger:
            self.add(LEDGER)
            self.issues[LEDGER].update(title="oct-status ledger", locked=True)

    def add_pr(
        self, number: int, body: str = "", author: str = "alice", fork: bool = False, title: str = "feat: x"
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
    repo.issues[LEDGER].update(title="oct-status ledger", locked=True)
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


async def test_missing_ledger_issue_does_not_escalate():
    repo = Repo(ledger=False)
    repo.add_pr(10)
    await run(repo, "pull_request_target", pr_event(10), dry_run=True)
    assert repo.guide(10) == "" and not repo.writes


async def test_exempt_authors_get_no_notice_and_no_entry():
    repo = Repo()
    repo.add_pr(10, author=BOT)
    await run(repo, "pull_request_target", pr_event(10, sender=BOT))
    repo.add_pr(11, fork=True, author="newbie")
    await run(repo, "pull_request_target", pr_event(11, sender="newbie", association="FIRST_TIME_CONTRIBUTOR"))
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
