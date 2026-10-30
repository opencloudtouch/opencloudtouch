"""Strike ledger (design section 10): one JSON comment per event on the locked ledger issue.

Ledger content is data, never instructions: every comment is parsed as JSON and validated field by
field, anything malformed or from an unexpected author is ignored. The counter is the number of
distinct (artifact, rule) pairs per user inside the rolling window, minus the pairs a maintainer
overrode. Strikes are inactive until ``cfg.strikes_enabled_from``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from .api import GitHubApi

if TYPE_CHECKING:
    from .config import Config
    from .violations import Violation

VERSION = 1
DEFAULT_WINDOW_DAYS = 60
MAX_REASON = 300
_PER_PAGE = 100
_MAX_PAGES = 50
_RULE = re.compile(r"V0[1-8]")
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
_CLOCK_SKEW = timedelta(days=1)  # entries dated further in the future are forged or broken


class LedgerError(Exception):
    """The ledger cannot be read or written; callers fail closed (no escalation)."""


@dataclass(frozen=True)
class Entry:
    kind: str  # "violation" or "override"
    user: str  # offender (violation) or the maintainer who overrode (override)
    artifact: int
    rule: str  # "" for an override, which covers every rule of the artifact
    ts: datetime
    reason: str = ""


def _parse(body: str) -> Entry | None:
    """A validated entry, or ``None`` for anything that is not exactly the expected shape."""
    try:
        data: Any = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("v") != VERSION:
        return None
    kind, user, artifact, ts = data.get("kind"), data.get("user"), data.get("artifact"), data.get("ts")
    if kind not in ("violation", "override") or not isinstance(user, str) or not _LOGIN.fullmatch(user):
        return None
    if not isinstance(artifact, int) or isinstance(artifact, bool) or artifact <= 0 or not isinstance(ts, str):
        return None
    rule = data.get("rule", "")
    if (kind == "violation") != (isinstance(rule, str) and bool(_RULE.fullmatch(rule))):
        return None
    reason = data.get("reason", "")
    try:
        when = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if when.tzinfo is None:
        return None
    return Entry(kind, user, artifact, rule, when, reason[:MAX_REASON] if isinstance(reason, str) else "")


class Ledger:
    """Reads and appends ledger entries; the entries are loaded once per instance."""

    def __init__(
        self,
        api: GitHubApi,
        issue_number: int,
        clock: Callable[[], datetime],
        *,
        cfg: Config | None = None,
        trusted_authors: tuple[str, ...] | None = None,
    ) -> None:
        self.api = api
        self.issue_number = issue_number
        self._clock = clock
        self._cfg = cfg
        self._trusted = trusted_authors if trusted_authors is not None else (cfg.bot_logins if cfg else None)
        self._window = timedelta(days=cfg.strike_window_days if cfg else DEFAULT_WINDOW_DAYS)
        self._entries: list[Entry] | None = None

    @property
    def active(self) -> bool:
        """Strikes count only from ``strikes_enabled_from`` on; without a config they always do."""
        if self._cfg is None:
            return True
        start = self._cfg.strikes_enabled_from
        return start is not None and self._clock().date() >= start

    async def load(self) -> list[Entry]:
        if self._entries is not None:
            return self._entries
        now = self._clock()
        since = (now - self._window).strftime("%Y-%m-%dT%H:%M:%SZ")
        found: list[Entry] = []
        try:
            for page in range(1, _MAX_PAGES + 1):
                resp = await self.api.request(
                    "GET",
                    f"/issues/{self.issue_number}/comments",
                    params={"since": since, "per_page": _PER_PAGE, "page": page},
                )
                resp.raise_for_status()
                batch = resp.json()
                for comment in batch:
                    author = (comment.get("user") or {}).get("login")
                    if self._trusted is not None and author not in self._trusted:
                        continue
                    entry = _parse(comment.get("body") or "")
                    if entry is not None and now - self._window <= entry.ts <= now + _CLOCK_SKEW:
                        found.append(entry)
                if len(batch) < _PER_PAGE:
                    break
        except (httpx.HTTPError, ValueError, AttributeError, TypeError) as exc:
            raise LedgerError(f"ledger issue #{self.issue_number} unreadable ({type(exc).__name__})") from exc
        self._entries = found
        return found

    @staticmethod
    def _pairs(entries: list[Entry], user: str) -> tuple[set[tuple[int, str]], set[tuple[int, str]]]:
        """(all pairs of `user`, those not overridden). An override covers earlier entries of its artifact."""
        overrides: dict[int, datetime] = {}
        for e in entries:
            if e.kind == "override" and e.ts >= overrides.get(e.artifact, e.ts):
                overrides[e.artifact] = e.ts
        mine = [e for e in entries if e.kind == "violation" and e.user == user]
        everything = {(e.artifact, e.rule) for e in mine}
        counted = {
            (e.artifact, e.rule) for e in mine if not (e.artifact in overrides and e.ts <= overrides[e.artifact])
        }
        return everything, counted

    async def level_for(self, user: str) -> int:
        """Number of counted strikes of `user` in the window; 0 while strikes are inactive."""
        if not self.active:
            return 0
        return len(self._pairs(await self.load(), user)[1])

    async def level_after(self, user: str, pairs: set[tuple[int, str]]) -> int:
        """The level `user` would have once `pairs` were recorded (for notices and dry-run)."""
        if not self.active:
            return 0
        everything, counted = self._pairs(await self.load(), user)
        return len(counted | (pairs - everything))

    async def is_overridden(self, user: str, artifact: int, rule: str) -> bool:
        everything, counted = self._pairs(await self.load(), user)
        return (artifact, rule) in everything and (artifact, rule) not in counted

    async def _append(self, entry: Entry, extra: dict[str, Any]) -> None:
        data = {"v": VERSION, "kind": entry.kind, "user": entry.user, "artifact": entry.artifact, **extra}
        data["ts"] = entry.ts.isoformat()
        try:
            resp = await self.api.request(
                "POST", f"/issues/{self.issue_number}/comments", json={"body": json.dumps(data, sort_keys=True)}
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LedgerError(f"ledger issue #{self.issue_number} not writable ({type(exc).__name__})") from exc
        (await self.load()).append(entry)

    async def record(self, v: Violation) -> bool:
        """Append a violation unless the (user, artifact, rule) pair is already in the window.

        Returns whether an entry was written. Nothing is recorded while strikes are inactive.
        """
        if not self.active:
            return False
        everything, _ = self._pairs(await self.load(), v.user)
        if (v.artifact, v.rule) in everything:
            return False
        entry = Entry("violation", v.user, v.artifact, v.rule, self._clock())
        await self._append(entry, {"rule": v.rule})
        return True

    async def record_override(self, user: str, artifact: int, reason: str) -> None:
        """Log an override by maintainer `user`; the strikes recorded so far on `artifact` stop counting."""
        entry = Entry("override", user, artifact, "", self._clock(), reason[:MAX_REASON])
        await self._append(entry, {"reason": entry.reason})
