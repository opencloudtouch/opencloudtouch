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
    maintainer_permissions: tuple[str, ...] = field(default=("maintain", "admin"))
    bot_logins: tuple[str, ...] = field(default=("oct-support", "github-actions[bot]"))


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
        maintainer_permissions=tuple(raw.get("maintainer_permissions", ("maintain", "admin"))),
        bot_logins=tuple(raw.get("bot_logins", ("oct-support", "github-actions[bot]"))),
    )
