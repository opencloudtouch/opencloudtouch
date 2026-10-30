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
    automation={**ACTIVE.automation, GITAR: Actor(GITAR, "automation", pushes=True)},
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

    def push(self, number: int, sha: str, author: str, files: list[str]) -> None:
        self.commits.setdefault(number, []).append({"sha": sha, "author": {"login": author}, "commit": {}})
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
