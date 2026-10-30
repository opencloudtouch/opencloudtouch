"""Fetch the facts of one issue or pull request into a Snapshot (read-only).

REST for everything; one GraphQL query for review threads, which REST cannot count.
Also fills pushes (PR commits), native sub-issues and blocked-by relations.
"""

from __future__ import annotations

import re
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


_TIMELINE_WINDOW = 50
_LABEL_NODES = "timelineItems(last: 50, itemTypes: [LABELED_EVENT]) { nodes { ... on LabeledEvent { label { name } actor { __typename login } } } }"
_LABELS_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!) { repository(owner: $owner, name: $name) {"
    " issueOrPullRequest(number: $number) { ... on Issue { %s } ... on PullRequest { %s } } } }"
    % (_LABEL_NODES, _LABEL_NODES)
)


def _is_bot(login: str, typename: str, cfg: Config) -> bool:
    """One of our own accounts: a configured login exactly, or an app whose REST login adds ``[bot]``.

    GraphQL reports apps without the suffix; only an actor of type ``Bot`` gets that mapping, so a
    user who happens to be called like an app is not trusted.
    """
    return login in cfg.bot_logins or (typename == "Bot" and f"{login}[bot]" in cfg.bot_logins)


async def _bot_phase_labels(
    api: GitHubApi, number: int, labels: frozenset[str], cfg: Config
) -> tuple[frozenset[str], frozenset[str], bool]:
    """(current phase labels last written by our own accounts, those last written by a person, whether the
    timeline was not conclusive).

    Only the newest 50 label events are read. When that window is full and some current phase label
    has no event in it, the history is incomplete and reported as unknown (nothing is trusted and
    callers fail closed). A label without any event in a short timeline is simply not ours (for
    example one renamed by the label sync; the backfill, MA-6, re-asserts those).
    """
    phases = {lb for lb in labels if lb.startswith("phase:")}
    if not phases:
        return frozenset(), frozenset(), False
    owner, name = api.repo.split("/", 1)
    try:
        data = await api.graphql(_LABELS_QUERY, {"owner": owner, "name": name, "number": number})
        item = ((data or {}).get("repository") or {}).get("issueOrPullRequest") or {}
        nodes = (item.get("timelineItems") or {}).get("nodes")
        if nodes is None:
            return frozenset(), frozenset(), True
        latest: dict[str, tuple[str, str]] = {}
        for node in nodes:
            label, actor = (node or {}).get("label"), (node or {}).get("actor") or {}
            if label and label.get("name"):
                latest[label["name"]] = (actor.get("login") or "", actor.get("__typename") or "")
    except (httpx.HTTPError, RuntimeError, AttributeError, TypeError, KeyError):
        return frozenset(), frozenset(), True
    if len(nodes) >= _TIMELINE_WINDOW and not phases <= set(latest):
        return frozenset(), frozenset(), True
    known = [lb for lb in phases if lb in latest and latest[lb][0]]
    ours = frozenset(lb for lb in known if _is_bot(*latest[lb], cfg))
    return ours, frozenset(known) - ours, False


_EDITS_QUERY = (
    "query($id: ID!) { node(id: $id) { ... on IssueComment { body author { __typename login }"
    " userContentEdits(last: 2) { nodes { createdAt editor { __typename login } } } } } }"
)


async def previous_version_is_ours(api: GitHubApi, node_id: str, edited_body: str, sender: str, cfg: Config) -> bool:
    """Whether the version a person's edit replaced was written by our own accounts (I5).

    GitHub's edit history (`userContentEdits`, newest last) must show: the comment still holds the
    edited text of the event (no later edit), the newest edit is the sender's, and the version before it
    was written by one of our accounts (the previous edit's editor, or the author when there was none).
    Anything else, including a GraphQL failure or a missing editor, is not verified (fail closed).
    """
    try:
        data = await api.graphql(_EDITS_QUERY, {"id": node_id})
        node = (data or {}).get("node") or {}
        nodes = [n or {} for n in ((node.get("userContentEdits") or {}).get("nodes") or [])]
        if not nodes or node.get("body") != edited_body:
            return False
        editors = [n.get("editor") or {} for n in nodes]
        if editors[-1].get("login") != sender:
            return False
        before = editors[-2] if len(editors) >= 2 else node.get("author") or {}
        login, typename = before.get("login") or "", before.get("__typename") or ""
    except (httpx.HTTPError, RuntimeError, AttributeError, TypeError, KeyError, ValueError):
        return False
    return bool(login) and _is_bot(login, typename, cfg)


async def _json(api: GitHubApi, path: str) -> Any:
    resp = await api.request("GET", path, params={"per_page": 100})
    resp.raise_for_status()
    return resp.json()


MAX_LIST_PAGES = 10  # pages of 100 per listing (reviews, check runs); beyond that only the newest are read
_LAST = re.compile(r'[?&]page=(\d+)[^>]*>;\s*rel="last"')


def _items(resp: httpx.Response, key: str | None) -> list[Any]:
    resp.raise_for_status()
    data = resp.json()
    return list((data or {}).get(key) or []) if key else list(data or [])


async def _listing(
    api: GitHubApi, path: str, what: str, key: str | None = None, warnings: list[str] | None = None
) -> list[Any]:
    """Every page of a chronological listing (100 per page), oldest first.

    GitHub names the last page in the ``Link`` header; when there are more than ``MAX_LIST_PAGES``
    pages, page 1 and the newest pages are read (the latest review of every user and the newest check
    runs are what the rules need) and `warnings` says so. Without a ``Link`` header pages are followed
    until a short one, up to the same cap.
    """

    async def page(n: int) -> httpx.Response:
        return await api.request("GET", path, params={"per_page": 100, "page": n})

    first = await page(1)
    items = _items(first, key)
    match = _LAST.search(first.headers.get("link", ""))
    if match:
        last = int(match[1])
        start = max(2, last - MAX_LIST_PAGES + 2)
        if start > 2 and warnings is not None:
            warnings.append(f"WARNING: {what} exceed {MAX_LIST_PAGES} pages; only the newest are read")
        for n in range(start, last + 1):
            items += _items(await page(n), key)
        return items
    batch, n = items, 1
    while len(batch) >= 100 and n < MAX_LIST_PAGES:
        n += 1
        batch = _items(await page(n), key)
        items += batch
    if len(batch) >= 100 and warnings is not None:
        warnings.append(f"WARNING: {what} exceed {MAX_LIST_PAGES} pages; later ones are not read")
    return items


async def author_permission(api: GitHubApi, user: str) -> str | None:
    resp = await api.request("GET", f"/collaborators/{user}/permission")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    # `permission` is the legacy four-value field (maintain shows as write, triage as read);
    # `role_name` carries the real role. Fall back to the legacy value when it is absent.
    role = data.get("role_name") or data.get("permission")
    return str(role) if role is not None else None


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
_MAX_FILE_PAGES = 30  # GitHub lists at most 3000 files per commit
UNKNOWN_PATHS = "<more-files-not-listed>"


async def _commit_paths(api: GitHubApi, sha: str) -> tuple[str, ...]:
    """Changed file paths of a commit (a renamed file with its previous path), paged; HTTP errors propagate.

    When 30 full pages were read, ``UNKNOWN_PATHS`` is appended as the last item: later rules
    must treat it as touching a protected path.
    """
    paths: list[str] = []
    for page in range(1, _MAX_FILE_PAGES + 1):
        resp = await api.request("GET", f"/commits/{sha}", params={"per_page": 100, "page": page})
        resp.raise_for_status()
        files = resp.json().get("files") or []
        for item in files:
            paths.append(item["filename"])
            if item.get("previous_filename"):  # a rename also touches the path it moved away from
                paths.append(item["previous_filename"])
        if len(files) < 100:
            return tuple(paths)
    return (*paths, UNKNOWN_PATHS)


async def _pushes(api: GitHubApi, number: int, cfg: Config | None) -> tuple[Push, ...]:
    """One Push per commit of the PR, oldest first; at most the newest 100 commits.

    GitHub's PR commits endpoint itself lists at most 250 commits. HTTP errors propagate.

    Author is the commit author login, else the committer login, else the git author name; the
    committer login is kept as well. File paths are fetched (``GET /commits/{sha}``) when the author
    or the committer is a pushing automation actor (``cfg.pushes``; an automation can commit a
    human-authored change); everybody else gets ``paths == ()``.
    """
    commits: list[dict[str, Any]] = []
    for page in range(1, _MAX_COMMIT_PAGES + 1):
        resp = await api.request("GET", f"/pulls/{number}/commits", params={"per_page": 100, "page": page})
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
        committer = (commit.get("committer") or {}).get("login") or ""
        paths: tuple[str, ...] = ()
        if cfg is not None and (cfg.pushes(login) or cfg.pushes(committer)):
            paths = await _commit_paths(api, commit["sha"])
        pushes.append(Push(commit["sha"], login, paths, committer))
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
    warnings: list[str] | None = None,
) -> Snapshot:
    """Facts of `number`; incomplete listings (more pages than the cap) are reported in `warnings`."""
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
            Review(
                (r.get("user") or {}).get("login", ""),
                r["state"],
                r.get("commit_id") or "",
                r.get("author_association") or "",
            )
            for r in await _listing(api, f"/pulls/{number}/reviews", f"reviews of #{number}", warnings=warnings)
        )
        what = f"check runs of #{number}"
        runs = await _listing(api, f"/commits/{head_sha}/check-runs", what, "check_runs", warnings)
        checks = tuple(
            Check(c["name"], c["status"], c.get("conclusion"), (c.get("app") or {}).get("slug", "")) for c in runs
        )
        drift = await _stack_drift(api, base_ref, head_ref, open_pr_heads)
        pushes = await _pushes(api, number, cfg)
        unresolved = await _unresolved_threads(api, number) if use_graphql else -1

    current_labels = frozenset(lb["name"] for lb in data.get("labels", []))
    bot_labels, human_labels, unknown = (
        await _bot_phase_labels(api, number, current_labels, cfg)
        if cfg is not None and use_graphql
        else (frozenset(), frozenset(), False)
    )
    return Snapshot(
        number=number,
        is_pr=is_pr,
        title=data["title"],
        body=body,
        state=data["state"],
        merged=bool(data.get("merged", False)),
        draft=bool(data.get("draft", False)),
        author=author,
        author_permission=await author_permission(api, author) if author else None,
        labels=current_labels,
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
        author_association=str(data.get("author_association") or ""),
        bot_phase_labels=bot_labels,
        human_phase_labels=human_labels,
        timeline_unknown=unknown,
    )
