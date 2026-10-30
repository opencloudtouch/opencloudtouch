"""Persistent guide notices and the protected-path acknowledgement (design sections 5a, 7 and 10).

The guide comment is regenerated on every run, so whatever has to outlive one run is stored in its
``<!-- oct-next-data {...} -->`` JSON: the open and recently resolved violation notices, and who
acknowledged automation pushes to protected paths up to which head. A notice stays open until it is
resolved: the label was healed (V02), the block restored (V03), the template keys came back (V05), a
later declaration was accepted (V07), the artifact was reopened or verified (V08), the pull request
no longer breaks the rule (V01, V04, V06), a maintainer overrode it, or it aged out of the window.

The data is untrusted input on the way back in (a person with write access can edit any comment):
it is only ever parsed as JSON, size-capped, validated field by field and scrubbed; anything that
does not match the expected shape is dropped. Nothing in it is executed or interpolated anywhere
but into the escaped guide text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from .apply import desired_labels
from .config import Config
from .guide import RESOLVED, WORKFLOW, format_notice
from .model import Derived, Graph, Phase, Snapshot
from .render import block_intact, extract_block
from .violations import KEY_CHARS, LEVEL_BLOCK, RULES, STATE_RULES, Notice, Violation, state_rules, template_keys

MAX_OPEN = 20
MAX_RESOLVED = 10
MAX_TEXT = 300
MAX_DATA = 64_000  # characters of JSON; larger data is unknown as a whole
DATA_BUDGET = 32_000  # characters of JSON the notices may take when written
_DATA = re.compile(r"<!-- oct-next-data (.*?) -->", re.DOTALL)
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:\[bot\])?")
_SHA = re.compile(r"[0-9a-f]{40}")
_UNSAFE = re.compile(r"[<>\x00-\x08\x0b-\x1f\x7f]")
_BOT = re.compile(r"@?gitar-bot(\[bot\])?", re.IGNORECASE)
# Mentions, images and links in stored text would notify people or load remote content when rendered.
_MARKUP = str.maketrans({"@": "\uff20", "[": "(", "]": ")"})
RESOLUTIONS = frozenset({"", "fixed", "restored", "accepted", "reopened", "verified", "overridden"})


@dataclass(frozen=True)
class Record:
    rule: str
    user: str
    artifact: int
    ts: datetime  # when the violation was (last) seen as an event, or first seen as a state
    level: int  # ladder level at detection, at least 1
    hint: str
    key: str = ""  # see `violations.Violation.key`
    resolved: str = ""  # "" while open, else one of RESOLUTIONS


@dataclass(frozen=True)
class Acceptance:
    sha: str
    by: str
    ts: datetime


@dataclass(frozen=True)
class GuideState:
    records: tuple[Record, ...] = ()
    accepted: Acceptance | None = None
    pending: str = ""  # head SHA the protected-path notice listed the files for (what accept-paths covers)


def scrub(text: str, limit: int = MAX_TEXT) -> str:
    """Idempotent cleaning of stored text: no HTML brackets, control characters, mentions, links or images."""
    cleaned = (_UNSAFE.sub(" ", _BOT.sub("the review bot", line)).translate(_MARKUP) for line in text.split("\n"))
    lines = [" ".join(line.split()) for line in cleaned]
    return "\n".join(line for line in lines if line)[:limit]


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        return None
    return when if when.tzinfo is not None else None


def _int(value: object, low: int, high: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        return None
    return value


def _record(raw: object) -> Record | None:
    if not isinstance(raw, dict):
        return None
    rule, user, hint, key, resolved = (raw.get(k) for k in ("rule", "user", "hint", "key", "resolved"))
    artifact, level, ts = _int(raw.get("artifact"), 1, 10**9), _int(raw.get("level"), 1, 99), _time(raw.get("ts"))
    if rule not in RULES or not isinstance(user, str) or not _LOGIN.fullmatch(user):
        return None
    if artifact is None or level is None or ts is None or not isinstance(hint, str):
        return None
    if not isinstance(key, str) or resolved not in RESOLUTIONS:
        return None
    return Record(str(rule), user, artifact, ts, level, scrub(hint), scrub(key, 1000), str(resolved))


def _acceptance(raw: object) -> Acceptance | None:
    if not isinstance(raw, dict):
        return None
    sha, by, ts = raw.get("sha"), raw.get("by"), _time(raw.get("ts"))
    if not isinstance(sha, str) or not _SHA.fullmatch(sha) or not isinstance(by, str) or not _LOGIN.fullmatch(by):
        return None
    return Acceptance(sha, by, ts) if ts is not None else None


def parse_state(body: str) -> GuideState | None:
    """The persisted state of a guide comment body, or ``None`` when it cannot be trusted as a whole.

    A missing, oversized or structurally invalid data block is unknown, not empty: the caller then
    does not rewrite the guide (which would wipe the notices) and the check fails closed. Single
    malformed records are dropped.
    """
    match = _DATA.search(body or "")
    if match is None or len(match[1]) > MAX_DATA:
        return None
    try:
        data = json.loads(match[1])
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("notices", []), list):
        return None
    records = [r for r in (_record(x) for x in data.get("notices", [])[: 4 * MAX_OPEN]) if r]
    pending = data.get("paths_pending")
    pending_sha = pending.get("sha") if isinstance(pending, dict) else None
    return GuideState(
        tuple(_cap(records)),
        _acceptance(data.get("paths_accepted")),
        pending_sha if isinstance(pending_sha, str) and _SHA.fullmatch(pending_sha) else "",
    )


def _record_data(r: Record) -> dict:
    return {
        "rule": r.rule,
        "user": r.user,
        "artifact": r.artifact,
        "ts": r.ts.isoformat(),
        "level": r.level,
        "hint": scrub(r.hint),
        "key": scrub(r.key, 1000),
        "resolved": r.resolved,
    }


def encode(data: object) -> str:
    """The data JSON exactly as the guide writes it: no ASCII escaping, `--` escaped (HTML comment)."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False).replace("--", "\\u002d\\u002d")


def _size(items: list[dict]) -> int:
    return len(encode(items))


def _within_budget(records: list[Record]) -> list[Record]:
    """Drop resolved records first, then the oldest open ones below ladder level 3 (never level 3+)."""
    kept = sorted(records, key=lambda r: r.ts)
    for droppable in (lambda r: bool(r.resolved), lambda r: not r.resolved and r.level < LEVEL_BLOCK):
        while _size([_record_data(r) for r in kept]) > DATA_BUDGET:
            victim = next((r for r in kept if droppable(r)), None)
            if victim is None:
                break
            kept.remove(victim)
    return kept


def state_data(records: list[Record], accepted: Acceptance | None, pending: str = "") -> dict:
    """The keys this module adds to the guide's data JSON (absent when there is nothing to keep)."""
    data: dict = {}
    if records:
        data["notices"] = [_record_data(r) for r in _within_budget(records)]
    if accepted is not None:
        data["paths_accepted"] = {"sha": accepted.sha, "by": accepted.by, "ts": accepted.ts.isoformat()}
    if pending:
        data["paths_pending"] = {"sha": pending}
    return data


def record_for(v: Violation, level: int, overridden: bool, now: datetime) -> Record:
    resolved = "overridden" if overridden else ""
    return Record(v.rule, v.user, v.artifact, now, max(level, 1), scrub(v.hint), scrub(v.key, 1000), resolved)


def _cap(records: list[Record]) -> list[Record]:
    """Keep the newest open and resolved records (oldest first, as stored)."""
    records = sorted(records, key=lambda r: r.ts)
    # Open notices at ladder level 3 or higher are never dropped: they block or revert.
    severe = [r for r in records if not r.resolved and r.level >= LEVEL_BLOCK]
    others = [r for r in records if not r.resolved and r.level < LEVEL_BLOCK]
    open_ = severe + others[-max(MAX_OPEN - len(severe), 0) :] if MAX_OPEN > len(severe) else severe
    done = [r for r in records if r.resolved][-MAX_RESOLVED:]
    return sorted(open_ + done, key=lambda r: r.ts)


def _resolution(rec: Record, snap: Snapshot, derived: Derived, graph: Graph, cfg: Config, accepted: set[str]) -> str:
    """Why an open record no longer holds, or "" while it does."""
    if rec.rule in STATE_RULES:
        return "" if rec.rule in state_rules(snap, graph, cfg) else "fixed"
    if rec.rule == "V02":
        return "restored" if (rec.key in snap.labels) == (rec.key in desired_labels(derived)) else ""
    if rec.rule == "V03":
        block = extract_block(snap.body)
        return "restored" if block is not None and block_intact(block) else ""
    if rec.rule == "V05":
        current = {scrub(k[:KEY_CHARS]) for k in template_keys(snap.body)}
        return "restored" if all(k in current for k in rec.key.split("\n") if k) else ""
    if rec.rule == "V07":
        return "accepted" if rec.key in accepted else ""
    if snap.state == "open":  # V08
        return "reopened"
    return "verified" if derived.phase != Phase.VERIFICATION else ""


def update(
    records: tuple[Record, ...] | list[Record],
    found: list[Record],
    snap: Snapshot,
    derived: Derived,
    graph: Graph,
    cfg: Config,
    now: datetime,
    accepted: set[str] | None = None,
    resolve: bool = True,
) -> list[Record]:
    """The records after this run: drop aged-out ones, merge `found`, resolve what no longer holds.

    `found` are the violations detected in this run (only for the event's artifact); `accepted` the
    names of commands accepted on the artifact in this run (`override` resolves every open notice).
    ``resolve=False`` keeps open records open: used for a guide a newer run wrote while this run's
    snapshot is older (judging them on stale facts could resolve them wrongly).
    """
    accepted = accepted or set()
    window = timedelta(days=cfg.strike_window_days)
    fresh = {(r.rule, r.user): r for r in found}
    out: list[Record] = []
    for rec in records:
        if now - rec.ts > window:
            continue
        new = fresh.pop((rec.rule, rec.user), None)
        if new is not None:
            if rec.resolved == "overridden" or new.resolved == "overridden":
                out.append(replace(rec, resolved="overridden"))  # an override covers a persisting violation
            elif rec.resolved or rec.rule not in STATE_RULES:
                out.append(replace(new, level=max(new.level, rec.level if not rec.resolved else 1)))
            else:
                out.append(replace(rec, level=new.level))
        elif rec.resolved:
            out.append(rec)
        else:
            reason = _resolution(rec, snap, derived, graph, cfg, accepted) if resolve else ""
            out.append(replace(rec, resolved=reason) if reason else rec)
    out += fresh.values()
    if "override" in accepted:
        out = [r if r.resolved else replace(r, resolved="overridden") for r in out]
    return _cap(out)


def render(records: list[Record], is_pr: bool) -> list[str]:
    """Guide notice texts, newest first; resolved ones start with ``[resolved] ``."""
    texts: list[str] = []
    for rec in sorted(records, key=lambda r: r.ts, reverse=True):
        notice = Notice(Violation(rec.rule, rec.artifact, rec.user, rec.hint, rec.key), rec.level)
        if not rec.resolved:
            texts.append(format_notice(notice, is_pr))
        elif rec.resolved == "overridden":
            texts.append(format_notice(replace(notice, overridden=True), is_pr))
        else:
            rule = RULES[rec.rule]
            link = f"[{rec.rule}]({WORKFLOW}#{rule.anchor})"
            texts.append(f"{RESOLVED}{link} {rule.title}: {rec.resolved}.")
    return texts


def blocking(records: list[Record] | tuple[Record, ...], is_pr: bool) -> list[Record]:
    """Open notices at ladder level 3 or higher on a pull request (the check `oct-status` fails)."""
    return [
        r
        for r in records
        if not r.resolved and Notice(Violation(r.rule, r.artifact, r.user, r.hint, r.key), r.level).blocks(is_pr)
    ]
