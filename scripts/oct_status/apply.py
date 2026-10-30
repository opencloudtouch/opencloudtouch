"""Idempotent applier: converge labels, status block and guide comment (design sections 4.3, 5, 5a).

Everything is diff-then-write: a second run on an unchanged artifact performs no write. The bot owns
only the ``phase:``, ``wait:`` and ``resolution:`` label namespaces.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .api import GitHubApi
from .config import Config
from .model import Derived, Snapshot
from .render import splice_block

MARKER = "<!-- oct-next:v1 -->"
OWNED_PREFIXES = ("phase:", "wait:", "resolution:")
PER_PAGE = 100


_OWN_ACTIONS = {"issues": {"edited", "labeled", "unlabeled"}}
_OWN_ACTIONS["pull_request"] = _OWN_ACTIONS["pull_request_target"] = _OWN_ACTIONS["issues"]


def is_own_event(event_name: str, payload: dict[str, Any], bot_logins: set[str]) -> bool:
    """Loop guard: True only for events our own writes cause (never reviews, checks or answers)."""
    if ((payload.get("sender") or {}).get("login")) not in bot_logins:
        return False
    action = payload.get("action")
    if event_name == "issue_comment":
        return action in {"created", "edited"} and MARKER in ((payload.get("comment") or {}).get("body") or "")
    return action in _OWN_ACTIONS.get(event_name, set())


def desired_labels(derived: Derived) -> set[str]:
    labels = {derived.phase.label, *(w.label for w in derived.waits)}
    if derived.resolution is not None:
        labels.add(derived.resolution.label)
    return labels


async def _check(resp: Any) -> Any:
    resp.raise_for_status()
    return resp


async def _comments(api: GitHubApi, number: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        resp = await _check(
            await api.request("GET", f"/issues/{number}/comments", params={"per_page": PER_PAGE, "page": page})
        )
        items = resp.json()
        out += items
        if len(items) < PER_PAGE:
            return out
        page += 1


async def _find_guides(api: GitHubApi, number: int, bot_logins: tuple[str, ...]) -> list[dict[str, Any]]:
    found = [
        c
        for c in await _comments(api, number)
        if MARKER in (c.get("body") or "") and (c.get("user") or {}).get("login") in bot_logins
    ]
    return sorted(found, key=lambda c: c["id"])  # oldest first


async def upsert_guide(
    api: GitHubApi, number: int, content: str, bot_logins: tuple[str, ...], *, dry_run: bool = False
) -> str:
    """Create, update or deduplicate the single guide comment; returns what was (or would be) done."""
    if MARKER not in content:  # the marker is what finds the comment again: exactly one, always
        content = f"{MARKER}\n{content}"
    guides = await _find_guides(api, number, bot_logins)
    if not guides:
        if not dry_run:
            await _check(await api.request("POST", f"/issues/{number}/comments", json={"body": content}))
        return "created"
    keep, extra = guides[0], guides[1:]
    for dup in extra:
        if not dry_run:
            await _check(await api.request("DELETE", f"/issues/comments/{dup['id']}"))
    changed = keep.get("body") != content
    if changed and not dry_run:
        await _check(await api.request("PATCH", f"/issues/comments/{keep['id']}", json={"body": content}))
    if extra:
        return "deduplicated"
    return "updated" if changed else "unchanged"


async def _sync_labels(api: GitHubApi, snap: Snapshot, derived: Derived, dry_run: bool) -> list[str]:
    want = desired_labels(derived)
    current = set(snap.labels)
    add = sorted(want - current)
    remove = sorted(label for label in current - want if label.startswith(OWNED_PREFIXES))
    if snap.timeline_unknown:
        # The phase was derived without trusting any fact label; never rewrite the phase from that.
        add = [lb for lb in add if not lb.startswith("phase:")]
        remove = [lb for lb in remove if not lb.startswith("phase:")]
    done: list[str] = []
    if add:
        if not dry_run:
            await _check(await api.request("POST", f"/issues/{snap.number}/labels", json={"labels": add}))
        done.append(f"add labels {', '.join(add)}")
    for name in remove:
        if not dry_run:
            await _check(await api.request("DELETE", f"/issues/{snap.number}/labels/{quote(name, safe='')}"))
        done.append(f"remove label {name}")
    return done


async def apply_state(
    api: GitHubApi,
    snap: Snapshot,
    derived: Derived,
    block: str | None,
    guide: str | None,
    cfg: Config,
    dry_run: bool = False,
) -> list[str]:
    """Converge the artifact to the derived state; returns the writes performed (planned if `dry_run`)."""
    if block is None and guide is None:  # announcements: nothing is ever written
        return []
    done = await _sync_labels(api, snap, derived, dry_run)
    actor = cfg.automation.get(snap.author)
    in_comment = actor is not None and actor.block_location == "comment"
    if block is not None and not in_comment:
        new_body = splice_block(snap.body, block)
        if new_body != snap.body:  # compare the spliced text: truncation changes the stored hash
            if not dry_run:
                await _check(await api.request("PATCH", f"/issues/{snap.number}", json={"body": new_body}))
            done.append("update status block in body")
    content = guide
    if block is not None and in_comment:
        content = f"{MARKER}\n{block}" if guide is None else f"{block}\n\n{guide}"
    if content is not None:
        result = await upsert_guide(api, snap.number, content, cfg.bot_logins, dry_run=dry_run)
        if result != "unchanged":
            done.append(f"guide comment {result}")
    return done
