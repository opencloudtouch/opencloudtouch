"""Fetch the facts of one issue or pull request into a Snapshot (read-only).

REST for everything; one GraphQL query for review threads, which REST cannot count.
Also fills pushes (PR commits), native sub-issues and blocked-by relations.
"""

from __future__ import annotations

from typing import Any

import httpx

from .api import GitHubApi
from .config import Config
from .graph import parse_prose_edges
from .model import Check, EdgeType, Push, Review, Snapshot

_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) { nodes { isResolved } }
    }
  }
}
"""


async def _json(api: GitHubApi, path: str) -> Any:
    resp = await api.request("GET", path, params={"per_page": 100})
    resp.raise_for_status()
    return resp.json()


async def _author_permission(api: GitHubApi, user: str) -> str | None:
    resp = await api.request("GET", f"/collaborators/{user}/permission")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    permission = resp.json().get("permission")
    return str(permission) if permission is not None else None


async def _stack_drift(api: GitHubApi, base: str, head: str, open_pr_heads: frozenset[str] | None) -> int | None:
    """Commits the PR branch is behind its base, only when the base is another open PR's head."""
    if not open_pr_heads or base not in open_pr_heads:
        return None
    resp = await api.request("GET", f"/compare/{base}...{head}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return int(resp.json().get("behind_by", 0))


_MAX_COMMIT_PAGES = 30  # safety bound against a server that ignores `page`


async def _pushes(api: GitHubApi, number: int, cfg: Config | None) -> tuple[Push, ...]:
    """One Push per commit of the PR, oldest first; at most the newest 100 commits.

    Author is the commit author login, else the committer login, else the git author name.
    File paths are fetched (``GET /commits/{sha}``) only for authors that are keys of
    ``cfg.automation``; everybody else gets ``paths == ()``.
    """
    commits: list[dict[str, Any]] = []
    for page in range(1, _MAX_COMMIT_PAGES + 1):
        resp = await api.request("GET", f"/pulls/{number}/commits", params={"per_page": 100, "page": page})
        if resp.status_code == 404:  # route not recorded/available: no push information
            break
        resp.raise_for_status()
        batch = resp.json()
        commits.extend(batch)
        if len(batch) < 100:
            break
    pushes: list[Push] = []
    for commit in commits[-100:]:
        login = (
            (commit.get("author") or {}).get("login")
            or (commit.get("committer") or {}).get("login")
            or ((commit.get("commit") or {}).get("author") or {}).get("name")
            or ""
        )
        paths: tuple[str, ...] = ()
        if cfg is not None and login in cfg.automation:
            detail = await api.request("GET", f"/commits/{commit['sha']}")
            if detail.status_code != 404:
                detail.raise_for_status()
                paths = tuple(f["filename"] for f in detail.json().get("files", []))
        pushes.append(Push(commit["sha"], login, paths))
    return tuple(pushes)


async def _issue_numbers(api: GitHubApi, path: str) -> tuple[int, ...]:
    """Numbers of the issues a relation endpoint lists; 404 or empty gives ``()``."""
    resp = await api.request("GET", path, params={"per_page": 100})
    if resp.status_code == 404:
        return ()
    resp.raise_for_status()
    return tuple(int(item["number"]) for item in resp.json())


async def _unresolved_threads(api: GitHubApi, number: int) -> int:
    """Unresolved review threads, or -1 (unknown) when GraphQL fails or answers unexpectedly."""
    owner, name = api.repo.split("/", 1)
    try:
        data = await api.graphql(_THREADS_QUERY, {"owner": owner, "name": name, "number": number})
    except (httpx.HTTPError, RuntimeError):  # transport/HTTP failure or an `errors` payload
        return -1
    repository = (data or {}).get("repository") or {}
    pull = repository.get("pullRequest") or {}
    nodes = (pull.get("reviewThreads") or {}).get("nodes")
    if nodes is None:
        return -1
    return sum(1 for node in nodes if not node["isResolved"])


def _linked_refs(number: int, body: str) -> tuple[int, ...]:
    """Targets of ``Closes``/``Part of`` phrases (REST has no closing-reference list)."""
    edges, _ = parse_prose_edges(number, body)
    return tuple(e.target for e in edges if e.type == EdgeType.IMPLEMENTS)


async def fetch_snapshot(
    api: GitHubApi,
    number: int,
    use_graphql: bool = True,
    open_pr_heads: frozenset[str] | None = None,
    cfg: Config | None = None,
) -> Snapshot:
    resp = await api.request("GET", f"/pulls/{number}")
    is_pr = resp.status_code != 404
    if is_pr:
        resp.raise_for_status()
        data = resp.json()
    else:
        data = await _json(api, f"/issues/{number}")

    author = (data.get("user") or {}).get("login", "")
    body = data.get("body") or ""
    base_ref = head_ref = head_sha = ""
    reviews: tuple[Review, ...] = ()
    checks: tuple[Check, ...] = ()
    unresolved = 0
    drift: int | None = None
    pushes: tuple[Push, ...] = ()
    is_fork = False
    if is_pr:
        base, head = data["base"], data["head"]
        base_ref, head_ref, head_sha = base["ref"], head["ref"], head["sha"]
        head_repo = (head.get("repo") or {}).get("full_name")
        base_repo = (base.get("repo") or {}).get("full_name")
        is_fork = head_repo is None or (base_repo is not None and head_repo != base_repo)
        reviews = tuple(
            Review((r.get("user") or {}).get("login", ""), r["state"], r.get("commit_id") or "")
            for r in await _json(api, f"/pulls/{number}/reviews")
        )
        runs = (await _json(api, f"/commits/{head_sha}/check-runs"))["check_runs"]
        checks = tuple(
            Check(c["name"], c["status"], c.get("conclusion"), (c.get("app") or {}).get("slug", "")) for c in runs
        )
        drift = await _stack_drift(api, base_ref, head_ref, open_pr_heads)
        pushes = await _pushes(api, number, cfg)
        unresolved = await _unresolved_threads(api, number) if use_graphql else -1

    return Snapshot(
        number=number,
        is_pr=is_pr,
        title=data["title"],
        body=body,
        state=data["state"],
        merged=bool(data.get("merged", False)),
        draft=bool(data.get("draft", False)),
        author=author,
        author_permission=await _author_permission(api, author) if author else None,
        labels=frozenset(lb["name"] for lb in data.get("labels", [])),
        base_ref=base_ref,
        head_ref=head_ref,
        head_sha=head_sha,
        reviews=reviews,
        unresolved_threads=unresolved,
        checks=checks,
        closing_refs=_linked_refs(number, body) if is_pr else (),
        sub_issues=await _issue_numbers(api, f"/issues/{number}/sub_issues"),
        blocked_by=await _issue_numbers(api, f"/issues/{number}/dependencies/blocked_by"),
        pushes=pushes,
        stack_drift=drift,
        head_is_fork=is_fork,
    )
