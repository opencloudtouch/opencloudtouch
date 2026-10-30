"""Loader for config.yml (actor allowlist, gate checks, protected paths)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml


@dataclass(frozen=True)
class Actor:
    login: str
    klass: Literal["automation", "human"]
    pushes: bool = False
    invalidates_approval: bool = True
    block_location: Literal["body", "comment"] = "body"


@dataclass(frozen=True)
class Config:
    automation: dict[str, Actor]
    gate_checks: list[str]
    protected_paths: list[str]
    fan_out_cap: int = 25
    strike_window_days: int = 60
    strikes_enabled_from: date | None = None
    ledger_issue: int | None = None  # number of the ledger issue; skips the search by title when set
    maintainer_permissions: tuple[str, ...] = field(default=("maintain", "admin"))
    bot_logins: tuple[str, ...] = field(default=("oct-support", "github-actions[bot]"))
    # Accounts whose ledger comments (and ledger issue) are trusted: exactly the writer. Ledger entries and
    # the ledger issue are written with BOT_PAT only (a run without it is forced to a dry run), never
    # with a job token, so `github-actions[bot]` (any workflow) is not trusted here.
    ledger_writers: tuple[str, ...] = field(default=("oct-support",))
    # Whether the legacy `wip` label (and, in the backfill, a hand-set `phase:in-progress` from its rename)
    # still proves that work started. Task 20 sets it to false once the backfill (MA-6) re-asserted those.
    legacy_wip_trusted: bool = True

    def pushes(self, login: str) -> bool:
        """Whether a commit by `login` is an automation push (an automation entry with ``pushes: true``)."""
        actor = self.automation.get(login)
        return actor is not None and actor.pushes


def load_config(path: Path) -> Config:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    automation: dict[str, Actor] = {}
    for login, opts in (raw.get("automation") or {}).items():
        opts = opts or {}
        automation[login] = Actor(
            login=login,
            klass=opts.get("klass", "automation"),
            pushes=bool(opts.get("pushes", False)),
            invalidates_approval=bool(opts.get("invalidates_approval", True)),
            block_location=opts.get("block_location", "body"),
        )
    ledger = raw.get("ledger_issue")
    if ledger is not None and (isinstance(ledger, bool) or not isinstance(ledger, int) or ledger <= 0):
        raise ValueError("config: ledger_issue must be a positive issue number or null")
    since = raw.get("strikes_enabled_from")
    if since is not None and not isinstance(since, date):
        since = date.fromisoformat(str(since))
    return Config(
        automation=automation,
        gate_checks=list(raw.get("gate_checks") or []),
        protected_paths=list(raw.get("protected_paths") or []),
        fan_out_cap=int(raw.get("fan_out_cap", 25)),
        strike_window_days=int(raw.get("strike_window_days", 60)),
        strikes_enabled_from=since,
        ledger_issue=ledger,
        maintainer_permissions=tuple(raw.get("maintainer_permissions", ("maintain", "admin"))),
        bot_logins=tuple(raw.get("bot_logins", ("oct-support", "github-actions[bot]"))),
        ledger_writers=tuple(raw.get("ledger_writers", ("oct-support",))),
        legacy_wip_trusted=bool(raw.get("legacy_wip_trusted", True)),
    )
