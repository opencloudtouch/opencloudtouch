"""Idempotent synchronisation of the status label taxonomy and the ledger issue."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

from oct_status.api import GitHubApi

LEDGER_TITLE = "oct-status ledger"
LEDGER_BODY = (
    "This issue is machine-written by the oct-status automation and is locked. "
    "It stores the status ledger; do not edit it by hand."
)


async def _paginate(api: GitHubApi, path: str, **params: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        resp = await api.request("GET", path, params={**params, "per_page": 100, "page": page})
        resp.raise_for_status()
        batch = resp.json()
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


async def _write(api: GitHubApi, method: str, path: str, **kw: Any) -> None:
    resp = await api.request(method, path, **kw)
    resp.raise_for_status()


async def _fetch_issue(api: GitHubApi, number: int) -> dict[str, Any]:
    resp = await api.request("GET", f"/issues/{number}")
    resp.raise_for_status()
    return dict(resp.json())


async def sync_labels(api: GitHubApi, spec_path: Path, dry_run: bool = False) -> list[str]:
    """Bring the repository labels in line with the spec; return performed or planned operations."""
    entries = (yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}).get("labels", [])
    current = {label["name"]: label for label in await _paginate(api, "/labels")}
    ops: list[str] = []
    for entry in entries:
        name: str = entry["name"]
        color: str = entry["color"].lower()
        description: str | None = entry.get("description")
        old = entry.get("rename_from")
        if name in current:
            existing = current[name]
            changes: dict[str, str] = {}
            if (existing.get("color") or "").lower() != color:
                changes["color"] = color
            if description is not None and (existing.get("description") or "") != description:
                changes["description"] = description
            if changes:
                ops.append(f"update {name}: {', '.join(sorted(changes))}")
                if not dry_run:
                    await _write(api, "PATCH", f"/labels/{quote(name, safe='')}", json=changes)
            continue
        if old and old in current:
            payload: dict[str, str] = {"new_name": name, "color": color}
            if description is not None:
                payload["description"] = description
            ops.append(f"rename {old} -> {name}")
            if not dry_run:
                await _write(api, "PATCH", f"/labels/{quote(old, safe='')}", json=payload)
            continue
        payload = {"name": name, "color": color, "description": description or ""}
        ops.append(f"create {name}")
        if not dry_run:
            await _write(api, "POST", "/labels", json=payload)
    return ops


class LedgerIssueError(Exception):
    """The configured ledger issue is not a usable ledger (wrong creator, a pull request)."""


async def ensure_ledger_issue(
    api: GitHubApi,
    dry_run: bool = False,
    *,
    bot_logins: tuple[str, ...] | None = None,
    configured: int | None = None,
) -> int:
    """Return the number of the locked ledger issue, creating and locking it if missing.

    `configured` (config.yml ``ledger_issue``) is verified with one request (not a pull request,
    created by one of `bot_logins`, locked) and used without any search. Otherwise the
    issue is found by title, and only an issue created by one of `bot_logins` counts: a stranger
    cannot plant a look-alike ledger. Without `bot_logins` the creator is not checked.
    """
    if configured:
        issue = await _fetch_issue(api, configured)
        if "pull_request" in issue or (
            bot_logins is not None and (issue.get("user") or {}).get("login") not in bot_logins
        ):
            raise LedgerIssueError(f"configured ledger issue #{configured} is not a bot-created issue")
        if not issue.get("locked") and not dry_run:
            await _write(api, "PUT", f"/issues/{configured}/lock", json={"lock_reason": "resolved"})
        return configured
    for issue in await _paginate(api, "/issues", state="all"):
        if issue.get("title") != LEDGER_TITLE or "pull_request" in issue:
            continue
        if bot_logins is not None and (issue.get("user") or {}).get("login") not in bot_logins:
            continue
        number = int(issue["number"])
        if not issue.get("locked") and not dry_run:
            await _write(api, "PUT", f"/issues/{number}/lock", json={"lock_reason": "resolved"})
        return number
    if dry_run:
        return 0
    resp = await api.request("POST", "/issues", json={"title": LEDGER_TITLE, "body": LEDGER_BODY})
    resp.raise_for_status()
    number = int(resp.json()["number"])
    await _write(api, "PUT", f"/issues/{number}/lock", json={"lock_reason": "resolved"})
    return number
