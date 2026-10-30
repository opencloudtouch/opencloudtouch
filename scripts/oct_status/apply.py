"""Idempotent applier: converge labels, status block and guide comment (design sections 4.3, 5, 5a).

Everything is diff-then-write: a second run on an unchanged artifact performs no write. The bot owns
only the ``phase:``, ``wait:`` and ``resolution:`` label namespaces.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from .api import GitHubApi
from .config import Config
from .model import Derived, Snapshot
from .render import splice_block

MARKER = "<!-- oct-next:v1 -->"
OWNED_PREFIXES = ("phase:", "wait:", "resolution:")
PER_PAGE = 100


_OWN_ACTIONS = {"issues": {"edited", "labeled", "unlabeled", "reopened"}}  # `reopened`: the V08 revert
_OWN_ACTIONS["pull_request"] = _OWN_ACTIONS["pull_request_target"] = {"edited", "labeled", "unlabeled"}


def is_guide_body(body: str | None) -> bool:
    """A guide comment starts with `MARKER` (after an optional BOM or whitespace); quoting it is not enough."""
    return (body or "").lstrip("\ufeff \t\r\n").startswith(MARKER)


def is_own_event(event_name: str, payload: dict[str, Any], bot_logins: set[str]) -> bool:
    """Loop guard: True only for events our own writes cause (never reviews, checks or answers)."""
    if ((payload.get("sender") or {}).get("login")) not in bot_logins:
        return False
    action = payload.get("action")
    if event_name == "issue_comment":
        return action in {"created", "edited"} and is_guide_body((payload.get("comment") or {}).get("body"))
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


def guides_in(comments: list[dict[str, Any]], bot_logins: tuple[str, ...]) -> list[dict[str, Any]]:
    """Our guide comments among `comments`, oldest first: written by one of `bot_logins` AND starting with
    `MARKER`. Another bot text that only quotes the marker (an issue-handler answer) is never adopted."""
    found = [c for c in comments if is_guide_body(c.get("body")) and (c.get("user") or {}).get("login") in bot_logins]
    return sorted(found, key=lambda c: c["id"])


async def _find_guides(api: GitHubApi, number: int, bot_logins: tuple[str, ...]) -> list[dict[str, Any]]:
    return guides_in(await _comments(api, number), bot_logins)


ANY = object()  # `expected` of `upsert_guide`: write whatever the comment holds now
CONFLICT = "conflict"


async def upsert_guide(
    api: GitHubApi,
    number: int,
    content: str,
    bot_logins: tuple[str, ...],
    *,
    dry_run: bool = False,
    expected: object = ANY,
) -> str:
    """Create, update or deduplicate the single guide comment; returns what was (or would be) done.

    `expected` is the guide body this run read (``None``: there was no guide). When the comment changed
    since (an overlapping run wrote newer notices), nothing is written and ``CONFLICT`` is returned, so
    an older state never overwrites a newer one.
    """
    if not is_guide_body(content):  # the leading marker is what finds the comment again
        content = f"{MARKER}\n{content}"
    guides = await _find_guides(api, number, bot_logins)
    if expected is not ANY and (guides[0].get("body") if guides else None) != expected:
        return CONFLICT
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
    """Add the missing owned labels and remove the stale ones.

    Names are compared case-insensitively, as GitHub does, so ``Phase:Ready`` is ``phase:ready`` and
    never churned. Removing a label that is already gone (404) counts as done.
    """
    want = {label.casefold(): label for label in desired_labels(derived)}
    current = {label.casefold(): label for label in snap.labels}
    add = sorted(label for key, label in want.items() if key not in current)
    remove = sorted(label for key, label in current.items() if key not in want and key.startswith(OWNED_PREFIXES))
    if snap.timeline_unknown:
        # The phase was derived without trusting any fact label; never rewrite the phase from that.
        add = [lb for lb in add if not lb.casefold().startswith("phase:")]
        remove = [lb for lb in remove if not lb.casefold().startswith("phase:")]
    done: list[str] = []
    if add:
        if not dry_run:
            await _check(await api.request("POST", f"/issues/{snap.number}/labels", json={"labels": add}))
        done.append(f"add labels {', '.join(add)}")
    for name in remove:
        if not dry_run:
            resp = await api.request("DELETE", f"/issues/{snap.number}/labels/{quote(name, safe='')}")
            if resp.status_code != 404:
                await _check(resp)
        done.append(f"remove label {name}")
    return done


def guide_content(snap: Snapshot, block: str | None, guide: str | None, cfg: Config) -> str | None:
    """The guide comment's text; where the block lives in the comment it follows the leading marker."""
    actor = cfg.automation.get(snap.author)
    if block is not None and actor is not None and actor.block_location == "comment":
        rest = guide.lstrip("\ufeff \t\r\n").removeprefix(MARKER).lstrip("\n") if guide is not None else ""
        return f"{MARKER}\n{block}" + (f"\n\n{rest}" if rest else "")
    return guide


async def _fresh_body(api: GitHubApi, number: int) -> str:
    resp = await _check(await api.request("GET", f"/issues/{number}"))
    return str(resp.json().get("body") or "")


async def _write_body(
    api: GitHubApi,
    snap: Snapshot,
    block: str,
    rerender: Callable[[str], str | None] | None,
    warnings: list[str] | None,
) -> bool:
    """PATCH the description with `block` spliced in, without losing an edit made since `snap` was read.

    GitHub has no conditional update for issues, so the body is read again right before the write: an
    unchanged body gets the planned text; a changed one gets the block (re-rendered from the new body by
    `rerender`, when given) spliced into it, after one more read confirms it is stable. A body that
    changed again is not written (warning): the edit's own event recomputes the block. Returns whether
    the description was written.
    """
    expected = snap.body
    for attempt in range(2):
        fresh = await _fresh_body(api, snap.number)
        if fresh == expected:
            new_body = splice_block(fresh, block)
            if new_body == fresh:
                return False
            await _check(await api.request("PATCH", f"/issues/{snap.number}", json={"body": new_body}))
            return True
        if attempt == 0:
            expected = fresh
            if rerender is not None:
                fresh_block = rerender(fresh)
                if fresh_block is None:
                    return False
                block = fresh_block
            if splice_block(fresh, block) == fresh:  # an overlapping run already wrote it
                return False
    if warnings is not None:
        warnings.append(f"WARNING: description of #{snap.number} changed during this run; status block not rewritten")
    return False


async def apply_state(
    api: GitHubApi,
    snap: Snapshot,
    derived: Derived,
    block: str | None,
    guide: str | None,
    cfg: Config,
    dry_run: bool = False,
    *,
    comments: bool = True,
    expected_guide: object = ANY,
    rerender: Callable[[str], str | None] | None = None,
    warnings: list[str] | None = None,
) -> list[str]:
    """Converge the artifact to the derived state; returns the writes performed (planned if `dry_run`).

    With ``comments=False`` no comment is created or edited (backfill: no notifications; and when the
    persisted guide state could not be read): a block that lives in the pinned comment is not written.
    A guide that changed since `expected_guide` was read is not written: "guide comment conflict".
    The description is re-read before it is written (``_write_body``): `rerender` renders the block
    for a description edited meanwhile, and `warnings` collects a skipped write.
    """
    if block is None and guide is None:  # announcements: nothing is ever written
        return []
    done = await _sync_labels(api, snap, derived, dry_run)
    actor = cfg.automation.get(snap.author)
    in_comment = actor is not None and actor.block_location == "comment"
    if block is not None and not in_comment:
        new_body = splice_block(snap.body, block)
        if new_body != snap.body:  # compare the spliced text: truncation changes the stored hash
            if dry_run or await _write_body(api, snap, block, rerender, warnings):
                done.append("update status block in body")
    content = guide_content(snap, block, guide, cfg)
    if content is not None and comments:
        result = await upsert_guide(api, snap.number, content, cfg.bot_logins, dry_run=dry_run, expected=expected_guide)
        if result != "unchanged":
            done.append(f"guide comment {result}")
    return done
