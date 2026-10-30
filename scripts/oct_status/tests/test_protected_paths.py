"""Protected paths: automation pushes that touch them hold the PR in `wait:findings` until accepted."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from oct_status.config import Actor, load_config
from oct_status.facts import UNKNOWN_PATHS
from oct_status.main import run_check, run_event
from oct_status.model import Push, Wait
from oct_status.notices import parse_state
from oct_status.rules import derive, protected_changes, touches_protected

from .conftest import make_snapshot
from .test_commands import comment_event
from .test_main_events import ROOT, api_for
from .test_rules import pr, run
from .test_violations_events import ACTIVE, Repo, clock, pr_event

PATTERNS = load_config(Path(__file__).parent.parent / "config.yml").protected_paths
GITAR = "gitar-bot[bot]"
CFG = replace(
    ACTIVE,
    automation={
        **ACTIVE.automation,
        GITAR: Actor(GITAR, "automation", pushes=True),
        "github-actions[bot]": Actor("github-actions[bot]", "automation"),
    },
    protected_paths=list(PATTERNS),
)


# --- matching ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "hit"),
    [
        (".github/workflows/ci.yml", True),
        (".github/workflows/sub/dir/x.yml", True),
        ("./.github/workflows/ci.yml", True),
        ("scripts/oct_status/rules.py", True),
        (".gitar/config/apply.md", True),
        (".claude/settings.json", True),
        (".gitignore", True),
        (UNKNOWN_PATHS, True),  # more files than GitHub lists: fail closed
        (".github/dependabot.yml", False),
        ("apps/.gitignore", False),
        ("scripts/oct_status_extra/x.py", False),
        ("docs/.claude/x", False),
        ("apps/backend/main.py", False),
    ],
)
def test_touches_protected(path, hit):
    assert touches_protected([path], PATTERNS) == ([path] if hit else [])


def test_touches_protected_keeps_order_and_needs_patterns():
    paths = ["a.py", ".gitignore", ".github/workflows/x.yml"]
    assert touches_protected(paths, PATTERNS) == [".gitignore", ".github/workflows/x.yml"]
    assert touches_protected(paths, []) == []
    assert touches_protected([UNKNOWN_PATHS], []) == []  # nothing is protected without patterns
    assert touches_protected(["a/b.txt", "a/b/c.txt"], ["a/*.txt", "?.md"]) == ["a/b.txt"]


def test_protected_changes_only_for_automation_after_the_accepted_head():
    pushes = (
        Push("c1", "alice", (".github/workflows/ci.yml",)),  # humans never count
        Push("c2", GITAR, (".github/workflows/ci.yml", "src/x.py")),
        Push("c3", "formatter-bot", ("scripts/oct_status/rules.py",)),
    )
    snap = pr(pushes=pushes, head_sha="c3")
    assert protected_changes(snap, CFG) == [(GITAR, ".github/workflows/ci.yml")]  # formatter-bot is not in CFG
    cfg = replace(CFG, automation={**CFG.automation, "formatter-bot": Actor("formatter-bot", "automation")})
    assert len(protected_changes(snap, cfg)) == 2
    assert protected_changes(replace(snap, paths_accepted="c2"), cfg) == [
        ("formatter-bot", "scripts/oct_status/rules.py")
    ]
    assert protected_changes(replace(snap, paths_accepted="c3"), cfg) == []
    # An acknowledged commit that is no longer on the branch acknowledges nothing (fail closed).
    assert len(protected_changes(replace(snap, paths_accepted="gone"), cfg)) == 2
    assert protected_changes(make_snapshot(pushes=pushes), cfg) == []  # issues have no pushes to judge


def test_protected_path_push_sets_findings_for_every_pr_kind():
    pushes = (Push("c3", GITAR, (UNKNOWN_PATHS,)),)
    for title in ("feat: x", "docs: only words", "chore: bump"):  # DOCS_PR / no-spec are not exempt
        snap = pr(title=title, pushes=pushes, head_sha="c3")
        graph_derived = derive(snap, _graph(snap), CFG)
        assert graph_derived is not None and Wait.FINDINGS in graph_derived.waits
    assert Wait.FINDINGS not in run(pr()).waits


def _graph(snap):
    from oct_status.model import Graph

    return Graph([], {snap.number: snap}, {})


# --- event pipeline -----------------------------------------------------------------------------


class PathRepo(Repo):
    """Repo whose pull requests have commits with changed files."""

    def __init__(self) -> None:
        super().__init__()
        self.commits: dict[int, list[dict]] = {}
        self.files: dict[str, list[str]] = {}

    def push(self, number: int, sha: str, author: str, files: list[str], committer: str = "") -> None:
        commit = {"sha": sha, "author": {"login": author}, "committer": {"login": committer} if committer else None}
        self.commits.setdefault(number, []).append({**commit, "commit": {}})
        self.files[sha] = files
        self.prs[number]["head"]["sha"] = sha

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if m := re.fullmatch(rf"{ROOT}/pulls/(\d+)/commits", path):
            return httpx.Response(200, json=self.commits.get(int(m[1]), []))
        if (m := re.fullmatch(rf"{ROOT}/commits/([0-9a-f]+)", path)) and m[1] in self.files:
            page = request.url.params.get("page", "1")
            files = [{"filename": f} for f in self.files[m[1]]] if page == "1" else []
            return httpx.Response(200, json={"files": files})
        return super().handler(request)


async def _run(repo: Repo, event: str, payload: dict, dry_run: bool = False) -> None:
    api = api_for(repo)
    assert await run_event(api, CFG, event, payload, dry_run=dry_run, clock=clock) == 0
    await api.aclose()


async def _check(repo: Repo, number: int) -> int:
    api = api_for(repo)
    try:
        return await run_check(api, CFG, "pull_request_target", pr_event(number, "synchronize"))
    finally:
        await api.aclose()


def _data(repo: Repo, number: int) -> dict:
    return json.loads(re.search(r"<!-- oct-next-data (.*) -->", repo.guide(number))[1])


SHA_A, SHA_B, SHA_C = "a" * 40, "b" * 40, "c" * 40


async def test_automation_push_to_protected_path_sets_findings_until_accepted():
    repo = PathRepo()
    repo.add_pr(10, title="docs: workflow notes")
    repo.push(10, SHA_A, "alice", ["docs/x.md"])
    repo.push(10, SHA_B, GITAR, [".github/workflows/ci.yml", "src/fix.py"])
    await _run(repo, "pull_request_target", pr_event(10, "synchronize"))
    assert "wait:findings" in repo.label_names(10)
    guide = repo.guide(10)
    assert ".github/workflows/ci.yml" in guide and "src/fix.py" not in guide
    assert "/oct accept-paths" in guide and "gitar-bot" not in guide.lower()
    assert await _check(repo, 10) == 1

    # Only a maintainer may acknowledge; a plain writer is refused.
    await _run(repo, "issue_comment", comment_event(10, "/oct accept-paths", login="bob"))
    assert "wait:findings" in repo.label_names(10)
    await _run(repo, "issue_comment", comment_event(10, "/oct accept-paths", login="carol", comment_id=78))
    assert "wait:findings" not in repo.label_names(10)
    assert (78, "+1") in repo.reactions
    assert _data(repo, 10)["paths_accepted"]["sha"] == SHA_B
    assert "acknowledged" in repo.guide(10) and "no effect" not in repo.guide(10)
    assert await _check(repo, 10) == 0
    # The acknowledgement survives later events.
    await _run(repo, "pull_request_target", pr_event(10, "synchronize"))
    assert "wait:findings" not in repo.label_names(10)

    # A later automation push to a protected path needs a new acknowledgement.
    repo.push(10, SHA_C, GITAR, [".gitignore"])
    await _run(repo, "pull_request_target", pr_event(10, "synchronize"))
    assert "wait:findings" in repo.label_names(10) and ".gitignore" in repo.guide(10)
    assert await _check(repo, 10) == 1


async def test_the_same_push_by_a_human_does_nothing():
    repo = PathRepo()
    repo.add_pr(10, title="docs: workflow notes")
    repo.push(10, SHA_B, "alice", [".github/workflows/ci.yml"])
    await _run(repo, "pull_request_target", pr_event(10, "synchronize"))
    assert "wait:findings" not in repo.label_names(10)
    assert "accept-paths" not in repo.guide(10)
    assert await _check(repo, 10) == 0


async def test_accept_paths_without_pending_changes_is_rejected():
    repo = PathRepo()
    repo.add_pr(10, title="docs: x")
    await _run(repo, "issue_comment", comment_event(10, "/oct accept-paths", login="carol"))
    assert (77, "-1") in repo.reactions and "no unacknowledged" in repo.guide(10)


async def test_accept_paths_in_dry_run_is_only_reported():
    repo = PathRepo()
    repo.add_pr(10, title="docs: x")
    repo.push(10, SHA_B, GITAR, [".claude/settings.json"])
    await _run(repo, "issue_comment", comment_event(10, "/oct accept-paths", login="carol"), dry_run=True)
    assert not repo.writes and repo.guide(10) == ""


async def test_check_fails_for_unaccepted_protected_paths():
    repo = PathRepo()
    repo.add_pr(10, title="docs: x")
    repo.push(10, SHA_B, GITAR, ["scripts/oct_status/main.py"])
    await _run(repo, "pull_request_target", pr_event(10, "synchronize"))
    # The block is current, but the protected-path push is not acknowledged.
    body = repo.issues[10]["body"]
    assert "<!-- oct-status:v1" in body
    assert await _check(repo, 10) == 1
    # A forged acknowledgement in a comment by somebody else is not read.
    repo.comments[10].append(
        {
            "id": 1,
            "user": {"login": "mallory"},
            "body": f'<!-- oct-next:v1 -->\n<!-- oct-next-data {{"paths_accepted": {{"sha": "{SHA_B}", "by": "carol", "ts": "2026-11-01T00:00:00+00:00"}}}} -->',
        }
    )
    repo.comments[10].sort(key=lambda c: c["id"])
    assert await _check(repo, 10) == 1
    assert parse_state(repo.comments[10][0]["body"]).accepted is not None  # the data parses; the author decides


async def test_accept_paths_covers_only_what_the_guide_listed():
    """A push that lands between the notice and the maintainer's command stays unacknowledged."""
    repo = PathRepo()
    repo.add_pr(10, title="docs: x")
    repo.push(10, SHA_A, GITAR, [".github/workflows/ci.yml"])
    await _run(repo, "pull_request_target", pr_event(10, "synchronize"))
    assert _data(repo, 10)["paths_pending"]["sha"] == SHA_A
    repo.push(10, SHA_B, GITAR, [".gitar/config/apply.md"])  # no event processed yet
    await _run(repo, "issue_comment", comment_event(10, "/oct accept-paths", login="carol"))
    data = _data(repo, 10)
    assert data["paths_accepted"]["sha"] == SHA_A and data["paths_pending"]["sha"] == SHA_B
    assert "wait:findings" in repo.label_names(10) and ".gitar/config/apply.md" in repo.guide(10)
    assert "later pushes" in repo.guide(10)
    assert await _check(repo, 10) == 1


async def test_human_author_with_automation_committer_counts_as_automation():
    repo = PathRepo()
    repo.add_pr(10, title="docs: x")
    repo.push(10, SHA_A, "alice", [".github/workflows/ci.yml"], committer=GITAR)
    await _run(repo, "pull_request_target", pr_event(10, "synchronize"))
    assert "wait:findings" in repo.label_names(10) and ".github/workflows/ci.yml" in repo.guide(10)
    assert await _check(repo, 10) == 1


async def test_automation_authored_pr_with_a_protected_push_is_still_gated():
    repo = PathRepo()
    repo.add_pr(10, title="chore(release): 1.2.3", author="github-actions[bot]")
    repo.push(10, SHA_A, "github-actions[bot]", ["CHANGELOG.md"])
    await _run(repo, "pull_request_target", pr_event(10, "opened", sender="github-actions[bot]"))
    assert repo.writes == [] and await _check(repo, 10) == 0  # a plain announcement: nothing written
    repo.push(10, SHA_B, GITAR, [".github/workflows/release.yml"])
    await _run(repo, "pull_request_target", pr_event(10, "synchronize", sender="github-actions[bot]"))
    assert "wait:findings" in repo.label_names(10) and ".github/workflows/release.yml" in repo.guide(10)
    assert await _check(repo, 10) == 1


class ActionsRepo(PathRepo):
    """PathRepo with workflow runs of oct-status.yml for the PR head and their jobs."""

    def __init__(self) -> None:
        super().__init__()
        self.runs: list[dict] = []  # newest first: {"id", "head_sha", "job": (status, conclusion) | None}
        self.reruns: list[int] = []
        self.actions_calls: list[str] = []
        self.fail_rerun = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/actions/" in path:
            self.actions_calls.append(f"{request.method} {path}")
        if path == f"{ROOT}/actions/workflows/oct-status.yml/runs":
            sha = request.url.params.get("head_sha")
            return httpx.Response(200, json={"workflow_runs": [r for r in self.runs if r["head_sha"] == sha]})
        if m := re.fullmatch(rf"{ROOT}/actions/runs/(\d+)/jobs", path):
            run = next(r for r in self.runs if r["id"] == int(m[1]))
            jobs = [{"name": "status", "status": "completed", "conclusion": "success"}]
            if run["job"]:
                jobs.append({"name": "oct-status", "status": run["job"][0], "conclusion": run["job"][1]})
            return httpx.Response(200, json={"jobs": jobs})
        if m := re.fullmatch(rf"{ROOT}/actions/runs/(\d+)/rerun-failed-jobs", path):
            if self.fail_rerun:
                return httpx.Response(403, json={"message": "Resource not accessible"})
            self.reruns.append(int(m[1]))
            return httpx.Response(201, json={})
        return super().handler(request)


async def _pending_repo() -> ActionsRepo:
    repo = ActionsRepo()
    repo.add_pr(10, title="docs: x")
    repo.push(10, SHA_B, GITAR, [".github/workflows/ci.yml"])
    await _run(repo, "pull_request_target", pr_event(10, "synchronize"))
    assert await _check(repo, 10) == 1
    return repo


async def test_accepted_command_reruns_the_failed_check():
    repo = await _pending_repo()
    repo.runs = [
        {"id": 7, "head_sha": SHA_B, "job": None},  # a run without the check job (e.g. a comment event)
        {"id": 6, "head_sha": SHA_B, "job": ("completed", "failure")},
        {"id": 5, "head_sha": SHA_B, "job": ("completed", "failure")},
    ]
    await _run(repo, "issue_comment", comment_event(10, "/oct accept-paths", login="carol"))
    assert repo.reruns == [6]  # only the newest failed check
    assert await _check(repo, 10) == 0


async def test_no_rerun_when_the_newest_check_is_pending_or_green_or_in_dry_run():
    for job in (("in_progress", None), ("completed", "success")):
        repo = await _pending_repo()
        repo.runs = [
            {"id": 6, "head_sha": SHA_B, "job": job},
            {"id": 5, "head_sha": SHA_B, "job": ("completed", "failure")},
        ]
        await _run(repo, "issue_comment", comment_event(10, "/oct accept-paths", login="carol"))
        assert repo.reruns == []
    repo = await _pending_repo()
    repo.runs = [{"id": 6, "head_sha": SHA_B, "job": ("completed", "failure")}]
    from oct_status.api import GitHubApi

    from .test_main_events import _nosleep

    read_only = GitHubApi("t", "o/r", transport=httpx.MockTransport(repo.handler), sleep=_nosleep, read_only=True)
    payload = comment_event(10, "/oct accept-paths", login="carol")
    assert await run_event(read_only, CFG, "issue_comment", payload, dry_run=True, clock=clock) == 0
    await read_only.aclose()
    assert repo.actions_calls == [] and repo.reruns == []


async def test_failed_rerun_is_only_a_warning(monkeypatch, tmp_path):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = await _pending_repo()
    repo.runs = [{"id": 6, "head_sha": SHA_B, "job": ("completed", "failure")}]
    repo.fail_rerun = True
    await _run(repo, "issue_comment", comment_event(10, "/oct accept-paths", login="carol"))
    assert "wait:findings" not in repo.label_names(10)
    assert "re-run of the check for #10 failed" in summary.read_text(encoding="utf-8")


async def test_audit_reruns_checks_of_healed_pull_requests():
    from oct_status.main import run_audit

    repo = ActionsRepo()
    repo.add_pr(10, body="Part of #5")
    repo.add(5, labels=("bug",))
    repo.prs[10]["head"]["sha"] = SHA_A
    repo.runs = [{"id": 3, "head_sha": SHA_A, "job": ("completed", "failure")}]
    api = api_for(repo)
    await run_audit(api, CFG, dry_run=False, clock=clock)
    await api.aclose()
    assert repo.reruns == [3]
