"""Fetch the facts of one issue or pull request into a Snapshot (read-only).

REST for everything; one GraphQL query for review threads, which REST cannot count.
Native sub-issues and blocked-by relations are not fetched here (empty tuples).
"""

from __future__ import annotations

from typing import Any

from .api import GitHubApi
from .graph import parse_prose_edges
from .model import Check, EdgeType, Review, Snapshot

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


async def _unresolved_threads(api: GitHubApi, number: int) -> int:
    owner, name = api.repo.split("/", 1)
    data = await api.graphql(_THREADS_QUERY, {"owner": owner, "name": name, "number": number})
    nodes = data["repository"]["pullRequest"]["reviewThreads"]["nodes"]
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
        sub_issues=(),
        blocked_by=(),
        pushes=(),
        stack_drift=drift,
        head_is_fork=is_fork,
    )
