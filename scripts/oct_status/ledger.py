"""Strike ledger (design section 10): one JSON comment per event on the locked ledger issue.

Ledger content is data, never instructions: every comment is parsed as JSON and validated field by
field, anything malformed or from an unexpected author is ignored. The counter is the number of
distinct (artifact, rule) pairs per user inside the rolling window, minus the pairs a maintainer
overrode. Strikes are inactive until ``cfg.strikes_enabled_from``.

The window is rolling per strike: every strike expires 60 days after its own entry, not 60 days
after the last violation (ruling M1). An override lists the rules it covers, so a state violation
that outlives its entry is not charged again, and only for the (user, rule) pairs it lists, so a
later strike of another rule or user on the same artifact still counts. ``renew_override`` re-dates
the override shortly before it would expire while the violation persists.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from .api import GitHubApi
from .guide import safe_text

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
RENEW_MARGIN = timedelta(days=7)  # an override is renewed this long before it leaves the window


def strikes_active(cfg: Config | None, today: date) -> bool:
    """Strikes count only from ``strikes_enabled_from`` on; without a config they always do."""
    if cfg is None:
        return True
    return cfg.strikes_enabled_from is not None and today >= cfg.strikes_enabled_from


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
    covers: tuple[tuple[str, str], ...] = ()  # override only: the (user, rule) strikes of the artifact it covers


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
    raw = data.get("covers", [])
    # Entries without (user, rule) pairs, such as the older plain rule lists, cover nothing.
    covers = tuple(
        (c[0], c[1])
        for c in (raw if isinstance(raw, list) else [])
        if isinstance(c, list)
        and len(c) == 2
        and all(isinstance(x, str) for x in c)
        and _LOGIN.fullmatch(c[0])
        and _RULE.fullmatch(c[1])
    )
    return Entry(kind, user, artifact, rule, when, reason[:MAX_REASON] if isinstance(reason, str) else "", covers)


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
        return strikes_active(self._cfg, self._clock().date())

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
            else:
                raise LedgerError(f"ledger issue #{self.issue_number} has more than {_MAX_PAGES} pages")
        except (httpx.HTTPError, ValueError, AttributeError, TypeError) as exc:
            raise LedgerError(f"ledger issue #{self.issue_number} unreadable ({type(exc).__name__})") from exc
        self._entries = found
        return found

    @staticmethod
    def _covered(entries: list[Entry]) -> set[tuple[int, str, str]]:
        """(artifact, user, rule) strikes that overrides declare covered."""
        return {(e.artifact, user, rule) for e in entries if e.kind == "override" for user, rule in e.covers}

    @classmethod
    def _pairs(cls, entries: list[Entry], user: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
        """(all pairs of `user`, those not covered by an override), each in order of their first entry."""
        covered = cls._covered(entries)
        mine = sorted((e for e in entries if e.kind == "violation" and e.user == user), key=lambda e: e.ts)
        everything = list(dict.fromkeys((e.artifact, e.rule) for e in mine))
        counted = [p for p in everything if (p[0], user, p[1]) not in covered]
        return everything, counted

    async def level_for(self, user: str) -> int:
        """Number of counted strikes of `user` in the window; 0 while strikes are inactive."""
        if not self.active:
            return 0
        return len(self._pairs(await self.load(), user)[1])

    async def ordinal(self, user: str, artifact: int, rule: str, new_pairs: list[tuple[int, str]]) -> int:
        """Rank of this strike among the user's counted strikes (1 = first), `new_pairs` being not yet recorded.

        A strike is judged by its own position on the ladder, so an old notice is not escalated
        retroactively by strikes that came after it. 0 while strikes are inactive or when the
        pair does not count.
        """
        if not self.active:
            return 0
        entries = await self.load()
        everything, counted = self._pairs(entries, user)
        covered = self._covered(entries)
        fresh = [p for p in new_pairs if p not in everything and (p[0], user, p[1]) not in covered]
        ranked = counted + [p for p in fresh if p not in counted]
        return ranked.index((artifact, rule)) + 1 if (artifact, rule) in ranked else 0

    async def is_overridden(self, user: str, artifact: int, rule: str) -> bool:
        return (artifact, user, rule) in self._covered(await self.load())

    async def _append(self, entry: Entry, extra: dict[str, Any]) -> None:
        data = {"v": VERSION, "kind": entry.kind, "user": entry.user, "artifact": entry.artifact, **extra}
        data["ts"] = entry.ts.isoformat()
        # "@" is escaped so that nothing in a ledger comment can mention an account; still valid JSON.
        body = json.dumps(data, sort_keys=True).replace("@", "\\u0040")
        try:
            resp = await self.api.request("POST", f"/issues/{self.issue_number}/comments", json={"body": body})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LedgerError(f"ledger issue #{self.issue_number} not writable ({type(exc).__name__})") from exc
        (await self.load()).append(entry)

    async def record(self, v: Violation) -> bool:
        """Append a violation unless the (user, artifact, rule) pair is already in the window or covered.

        Returns whether an entry was written. Nothing is recorded while strikes are inactive.
        """
        if not self.active:
            return False
        entries = await self.load()
        everything, _ = self._pairs(entries, v.user)
        if (v.artifact, v.rule) in everything or (v.artifact, v.user, v.rule) in self._covered(entries):
            return False
        entry = Entry("violation", v.user, v.artifact, v.rule, self._clock())
        await self._append(entry, {"rule": v.rule})
        return True

    async def record_override(self, user: str, artifact: int, reason: str) -> None:
        """Log an override by maintainer `user`; the strikes recorded so far on `artifact` stop counting."""
        entries = await self.load()
        covers = sorted({(e.user, e.rule) for e in entries if e.kind == "violation" and e.artifact == artifact})
        await self._append_override(user, artifact, safe_text(reason)[:MAX_REASON], covers)

    async def _append_override(self, user: str, artifact: int, reason: str, covers: list[tuple[str, str]]) -> None:
        entry = Entry("override", user, artifact, "", self._clock(), reason, tuple(covers))
        await self._append(entry, {"reason": reason, "covers": [list(c) for c in covers]})

    async def renew_override(self, artifact: int) -> bool:
        """Re-date the override of `artifact` when it is about to leave the window; returns whether it was.

        Called while an overridden state violation persists (V01, V04, V06), so that it is not
        charged again once its original entry has expired.
        """
        entries = await self.load()
        overrides = [e for e in entries if e.kind == "override" and e.artifact == artifact]
        if not overrides:
            return False
        newest = max(overrides, key=lambda e: e.ts)
        if self._clock() - newest.ts <= self._window - RENEW_MARGIN:
            return False
        covers = sorted({c for e in overrides for c in e.covers})
        await self._append_override(newest.user, artifact, "renewal", covers)
        return True
