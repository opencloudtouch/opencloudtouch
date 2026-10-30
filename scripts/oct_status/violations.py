"""Violation detectors V01-V08 and the escalation ladder (design section 10). Everything here is pure.

A violation is a breach of the workflow rules by a person. Automation actors and first-time fork
contributors are exempt. The detectors only report; the ledger counts and the ladder decides what
the notice says. Blocking a pull request (``main.run_check``) and reverting an issue change
(``main._revert``) act on the flags of `Notice`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import Config
from .model import Derived, EdgeType, Graph, Kind, Phase, Snapshot
from .render import block_intact, extract_block
from .rules import detect_kind, spec_is_ready

EXEMPT_CLASSES = frozenset({"automation", "first-timer"})
FIRST_TIME_ASSOCIATIONS = frozenset({"FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER"})
# Labels the bot derives from facts (design section 4.3); declarations may be set by label.
FACT_PHASES = frozenset(
    f"phase:{p}" for p in ("new", "draft", "in-progress", "in-review", "merged", "done", "closed", "verification")
)
FACT_WAITS = frozenset(f"wait:{w}" for w in ("maintainer", "findings", "ci", "prerequisite", "hardware-test"))
FACT_LABELS = FACT_PHASES | FACT_WAITS
LEVEL_OVERRIDE_HINT = 2
LEVEL_BLOCK = 3
# Rules whose offending change the automation undoes on an issue: fact labels (V02) and the block (V03).
REVERTED_RULES = frozenset({"V02", "V03"})
STATE_RULES = frozenset({"V01", "V04", "V06"})
KEY_CHARS = 120  # a template key is stored (and compared) with at most this many characters


@dataclass(frozen=True)
class Rule:
    title: str
    anchor: str  # heading slug in docs/WORKFLOW.md
    expected: str
    steps: tuple[str, ...]


RULES: dict[str, Rule] = {
    "V01": Rule(
        "pull request without a spec",
        "v01-pull-request-without-a-spec",
        "Every pull request names the spec it implements, or states why none is needed.",
        ("Add `Part of #SPEC` or `Closes #<spec>` to the description.", "/oct no-spec REASON"),
    ),
    "V02": Rule(
        "fact label changed by hand",
        "v02-fact-label-changed-by-hand",
        "Phase and wait labels that describe facts are written by the status automation only.",
        ("Leave the label to the automation; it restores the derived value.", "/oct triage"),
    ),
    "V03": Rule(
        "status block edited by hand",
        "v03-status-block-edited-by-hand",
        "The oct-status block in the description is written by the automation only.",
        ("Do not edit between the oct-status markers; the automation restores the block.",),
    ),
    "V04": Rule(
        "ready pull request with an open prerequisite",
        "v04-ready-pull-request-with-an-open-prerequisite",
        "A pull request is marked ready only when its prerequisites are merged or it is stacked on them.",
        ("Retarget the PR onto its prerequisite's branch, or convert it back to a draft until that is merged.",),
    ),
    "V05": Rule(
        "template section or checklist item deleted",
        "v05-template-section-or-checklist-item-deleted",
        "Template sections and Definition of Ready / Done items stay; mark items that do not apply as `n/a`.",
        ("Restore the deleted section or item and write `n/a` plus the reason if it does not apply.",),
    ),
    "V06": Rule(
        "pull request for a spec that is not ready",
        "v06-pull-request-for-a-spec-that-is-not-ready",
        "Implementation starts after the spec is ready.",
        ("Complete the Definition of Ready of the spec and have it reviewed.", "/oct review"),
    ),
    "V07": Rule(
        "invalid declaration",
        "v07-invalid-declaration",
        "A declaration is made when its preconditions hold, for example a complete Definition of Ready.",
        ("Fix what the guide comment names, then repeat the command.",),
    ),
    "V08": Rule(
        "closed without hardware verification",
        "v08-closed-without-hardware-verification",
        "An artifact in verification is closed after `/oct verified`.",
        ("Reopen the artifact, verify on a device, then record it.", "/oct verified DEVICE"),
    ),
}


@dataclass(frozen=True)
class Violation:
    rule: str
    artifact: int
    user: str
    hint: str
    # What resolves an event violation later: the label (V02), the removed template keys (V05, one
    # per line) or the declaration command (V07). Empty for the other rules.
    key: str = ""


@dataclass(frozen=True)
class EventFacts:
    """What the webhook event says about the actor's own change (all from an untrusted payload)."""

    action: str = ""
    actor: str = ""
    label: str = ""
    body_before: str | None = None  # body before an `edited` event
    rejected: str | None = None  # a declaration command the actor sent and the automation rejected
    state_reason: str | None = None  # of a `closed` event: "completed" or "not_planned"
    closed_by_change: bool | None = None  # closed by a merged PR or a commit? ``None``: unknown


@dataclass(frozen=True)
class Notice:
    violation: Violation
    level: int  # effective ladder level, at least 1
    overridden: bool = False

    @property
    def override_hint(self) -> bool:
        return self.level >= LEVEL_OVERRIDE_HINT

    def blocks(self, is_pr: bool) -> bool:
        return self.level >= LEVEL_BLOCK and is_pr

    def revert(self, is_pr: bool) -> bool:
        """Issues cannot be blocked: at level 3 the change is undone where the automation can undo it."""
        return self.level >= LEVEL_BLOCK and not is_pr and self.violation.rule in REVERTED_RULES


def classify_actor(snap: Snapshot, cfg: Config) -> str:
    """ "automation", "first-timer" (first-time contributor on a fork pull request) or "human".

    The association is the one fetched with the snapshot, never one claimed by an event payload.
    """
    if snap.author in cfg.automation:
        return "automation"
    if snap.is_pr and snap.head_is_fork and snap.author_association in FIRST_TIME_ASSOCIATIONS:
        return "first-timer"
    return "human"


def anchor_for(rule: str) -> str:
    return RULES[rule].anchor


def _plain(text: str, limit: int = 120) -> str:
    """Single line without markup-significant characters, safe inside a Markdown sentence."""
    return " ".join(re.sub(r"[`<>\r\n\x00-\x1f]", " ", text).split())[:limit]


# --- helpers ---------------------------------------------------------------------------------------

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_ITEM = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s*(.*?)\s*$")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def template_keys(body: str) -> set[str]:
    """Template keys of a body outside the status block (public form for the notice resolution)."""
    return _template_keys(_without_block(body))


def _template_keys(body: str) -> set[str]:
    """Normalised headings and checklist items; filling an item in (text after a colon) keeps its key."""
    text = _COMMENT.sub("", body or "")
    keys: set[str] = set()
    for line in text.splitlines():
        if m := _HEADING.match(line):
            keys.add("h:" + " ".join(m[1].casefold().split()))
        elif m := _ITEM.match(line):
            keys.add("i:" + " ".join(m[1].split(":")[0].casefold().split()))
    return keys


def _without_block(body: str) -> str:
    block = extract_block(body)
    return body.replace(block, "") if block else body


def _is_open(snap: Snapshot) -> bool:
    return snap.state == "open" and not snap.merged


def _pull_request_rules(snap: Snapshot, graph: Graph, cfg: Config) -> list[tuple[str, str]]:
    """(rule, hint) of V01, V04 and V06: states of an open pull request, charged to its author."""
    if not snap.is_pr or not _is_open(snap):
        return []
    kind = detect_kind(snap, cfg)
    found: list[tuple[str, str]] = []
    implements = [e.target for e in graph.edges_of(snap.number, EdgeType.IMPLEMENTS)]
    # Kind.DOCS_PR (docs, ci, chore ... titles and `/oct no-spec`) needs no spec edge (design section 4.1).
    if kind == Kind.PULL_REQUEST and not implements and not snap.no_spec_reason:
        found.append(("V01", "This pull request has no `Part of #SPEC` or `Closes #SPEC` reference to a spec."))
    if not snap.draft:
        for edge in graph.edges_of(snap.number, EdgeType.DEPENDS_ON):
            target = graph.snapshots.get(edge.target)
            if target is None or not _is_open(target):
                continue
            if target.is_pr and target.head_ref and target.head_ref == snap.base_ref:
                continue  # declared as the stack parent
            found.append(("V04", f"#{edge.target} is still open and this pull request is not stacked on it."))
            break
    for number in implements:
        spec = graph.snapshots.get(number)
        if spec is not None and detect_kind(spec, cfg) == Kind.SPEC and not spec_is_ready(spec):
            found.append(("V06", f"Spec #{number} is not ready yet."))
            break
    return found


def state_rules(snap: Snapshot, graph: Graph, cfg: Config) -> set[str]:
    """Rules among V01, V04 and V06 that the pull request breaks right now."""
    return {rule for rule, _ in _pull_request_rules(snap, graph, cfg)}


def _event_rules(snap: Snapshot, derived: Derived, event: EventFacts) -> list[tuple[str, str, str]]:
    """(rule, hint, key) of V02, V03, V05, V07 and V08: the actor's own change in this event."""
    found: list[tuple[str, str, str]] = []
    if event.action in ("labeled", "unlabeled") and event.label in FACT_LABELS:
        verb = "added" if event.action == "labeled" else "removed"
        found.append(("V02", f"The label `{_plain(event.label)}` was {verb} by hand.", event.label))
    if event.action == "edited" and event.body_before is not None:
        block = extract_block(snap.body)
        # Judged on the body after the edit: the block must be present (it was before the edit) and
        # its content must match the hash in its own marker.
        if (block is None and extract_block(event.body_before) is not None) or (
            block is not None and not block_intact(block)
        ):
            found.append(("V03", "The oct-status block was changed or removed in the description.", ""))
        if snap.is_pr or "spec" in snap.labels:
            gone = sorted(_template_keys(_without_block(event.body_before)) - _template_keys(_without_block(snap.body)))
            if gone:
                names = ", ".join(_plain(k[2:], 40) for k in gone[:3])
                found.append(
                    ("V05", f"Removed from the description: {names}.", "\n".join(k[:KEY_CHARS] for k in gone[:5]))
                )
    if event.rejected:
        command = event.rejected.removeprefix("/oct ").split(" ", 1)[0]
        found.append(("V07", f"{_plain(event.rejected, 200)}.", command))
    if (
        event.action == "closed"
        and not snap.is_pr
        and snap.state == "closed"
        and event.state_reason == "completed"
        and event.closed_by_change is False  # unknown (None) fails closed: no strike
        and derived.phase == Phase.VERIFICATION
    ):
        found.append(("V08", "The artifact was closed while the hardware verification is still open.", ""))
    return found


def detect(
    snap: Snapshot,
    derived: Derived,
    graph: Graph,
    cfg: Config,
    actor_class: str,
    event: EventFacts | None = None,
) -> list[Violation]:
    """Violations visible now. `actor_class` classifies the artifact author (see ``classify_actor``).

    V01, V04 and V06 describe the state of a pull request and are charged to its author; V02, V03,
    V05, V07 and V08 describe the change in `event` and are charged to the person who made it.
    """
    out: list[Violation] = []
    author_exempt = actor_class in EXEMPT_CLASSES or snap.author in cfg.automation
    if not author_exempt and detect_kind(snap, cfg) != Kind.DEPENDENCY_PR:
        out += [Violation(rule, snap.number, snap.author, hint) for rule, hint in _pull_request_rules(snap, graph, cfg)]
    if event is not None and event.actor and event.actor not in cfg.automation and event.actor not in cfg.bot_logins:
        if not (event.actor == snap.author and author_exempt):
            out += [
                Violation(rule, snap.number, event.actor, hint, key)
                for rule, hint, key in _event_rules(snap, derived, event)
            ]
    return out


def escalate(v: Violation, level: int, overridden: bool = False) -> Notice:
    """The notice for `v` at ladder `level` (clamped to at least 1: a notice is always shown)."""
    return Notice(v, max(level, 1), overridden)
