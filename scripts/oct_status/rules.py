"""Kind detection and derivation of phase, waits and resolution (design sections 4 and 6).

Everything here is pure: no I/O, only the snapshot, its neighbours in the graph and the config.
"""

from __future__ import annotations

import re

from .config import Config
from .model import Check, Derived, EdgeType, Graph, Kind, Phase, Resolution, Review, Snapshot, Wait

DEPENDABOT = "dependabot[bot]"
_CHORE_TYPES = {"docs", "ci", "chore", "style", "test"}
_CONVENTIONAL = re.compile(r"^(\w+)(?:\([^)]*\))?!?:")


def detect_kind(snap: Snapshot, cfg: Config) -> Kind:
    """Artifact kind per design section 4.1; the first matching rule wins.

    Discussions are not fetched as issues, so ``DISCUSSION`` is never returned here.
    An issue without any kind label is treated as a feature request.
    """
    if snap.is_pr and snap.author == DEPENDABOT:
        return Kind.DEPENDENCY_PR
    if snap.author in cfg.automation:
        return Kind.ANNOUNCEMENT
    title = snap.title.lstrip().lower()
    if title.startswith("[tracking]"):
        return Kind.TRACKING
    if title.startswith("[test]"):
        return Kind.TEST_PLAN
    if snap.is_pr:
        match = _CONVENTIONAL.match(snap.title.strip())
        if snap.no_spec_reason or (match and match.group(1).lower() in _CHORE_TYPES):
            return Kind.DOCS_PR
        return Kind.PULL_REQUEST
    if "spec" in snap.labels:
        return Kind.SPEC
    if snap.labels & {"bug", "support"}:
        return Kind.BUG
    return Kind.FEATURE_REQUEST


# --- Declarations: commands, legal transitions, Definition of Ready ---------------------------

OCT_SUPPORT = "oct-support"
GITAR = "gitar-bot[bot]"
# Associations GitHub reports for users with write access to the repository.
_WRITE_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}

_TRANSITIONS: dict[Kind, dict[Phase, tuple[str, ...]]] = {
    Kind.SPEC: {
        Phase.DRAFT: ("review",),
        Phase.SPEC_REVIEW: ("rework", "ready"),
        Phase.SPEC_REWORK: ("review", "ready"),
    },
    Kind.BUG: {Phase.NEW: ("triage",), Phase.TRIAGED: ("confirm",)},
    Kind.FEATURE_REQUEST: {Phase.NEW: ("triage",)},
}
_COMMAND_PHASE = {
    "review": Phase.SPEC_REVIEW,
    "rework": Phase.SPEC_REWORK,
    "ready": Phase.READY,
    "triage": Phase.TRIAGED,
    "confirm": Phase.CONFIRMED,
}
# Declarations made by label only (no `/oct` command exists for them).
_LABEL_DECLARATIONS = {Kind.DISCUSSION: {Phase.NEEDS_SPEC, Phase.ANSWERED}, Kind.TEST_PLAN: {Phase.IN_PROGRESS}}
_DOR_GATED = {Phase.SPEC_REVIEW, Phase.READY}
_DEFAULT_PHASE = {Kind.SPEC: Phase.DRAFT, Kind.DISCUSSION: Phase.OPEN}
_READY_OR_LATER = {Phase.READY, Phase.IN_PROGRESS, Phase.IN_REVIEW, Phase.VERIFICATION, Phase.DONE}
_DECLARED_WAITS = {Wait.SPEC_FIX, Wait.REPORTER, Wait.DESIGNER}
_PHASE_ORDER = list(Phase)
# Fact phases the bot writes on an issue only once its work has started, which for a spec requires
# `ready`. They can be set by hand (V02), see `_declared_floor` for where they are trusted. The
# legacy `wip` label (renamed to `phase:in-progress` by the label sync) counts the same.
_STARTED = {Phase.IN_PROGRESS, Phase.IN_REVIEW, Phase.VERIFICATION, Phase.DONE, Phase.MERGED}
_STARTED_FLOOR = {Kind.SPEC: Phase.READY, Kind.BUG: Phase.TRIAGED, Kind.FEATURE_REQUEST: Phase.TRIAGED}

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_ITEM = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s*(.*?)\s*$")
_NOT_APPLICABLE = re.compile(r"\bn/a\b", re.IGNORECASE)


def legal_transitions(kind: Kind, phase: Phase) -> list[str]:
    """`/oct` commands that move an artifact of `kind` out of `phase` (state machine only).

    Preconditions such as a complete Definition of Ready are checked by the caller.
    """
    return list(_TRANSITIONS.get(kind, {}).get(phase, ()))


def _declarable(kind: Kind) -> set[Phase]:
    reachable = {_COMMAND_PHASE[c] for commands in _TRANSITIONS.get(kind, {}).values() for c in commands}
    return reachable | _LABEL_DECLARATIONS.get(kind, set())


def dor_status(body: str) -> tuple[bool, list[str]]:
    """Whether the `## Definition of Ready` checklist is complete, and its open items.

    An item counts as done when ticked or marked `n/a`. The level-3 heading rendered by the
    issue form is accepted too; the section ends at the next heading of the same or a higher level.
    """
    lines = (body or "").splitlines()
    level = start = 0
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and len(match[1]) in (2, 3) and match[2].lower() == "definition of ready":
            level, start = len(match[1]), index + 1
            break
    if not level:
        return False, ["Definition of Ready section missing"]
    items = 0
    open_items: list[str] = []
    for line in lines[start:]:
        heading = _HEADING.match(line)
        if heading and len(heading[1]) <= level:
            break
        item = _ITEM.match(line)
        if item:
            items += 1
            if item[1] == " " and not _NOT_APPLICABLE.search(item[2]):
                open_items.append(item[2])
    if not items:
        return False, ["Definition of Ready section has no checklist items"]
    return not open_items, open_items


def _labelled(snap: Snapshot, enum: type[Phase] | type[Wait] | type[Resolution]) -> list:
    prefix = enum.__name__.lower() + ":"
    values = {lb[len(prefix) :] for lb in snap.labels if lb.startswith(prefix)}
    return [member for member in enum if member.value in values]


def _declared_phase(snap: Snapshot, kind: Kind) -> Phase:
    """The furthest legal declared phase, else the kind's start phase."""
    for phase in reversed(_labelled(snap, Phase)):
        if phase not in _declarable(kind):
            continue
        if kind == Kind.SPEC and phase in _DOR_GATED and not dor_status(snap.body)[0]:
            continue
        return phase
    return _DEFAULT_PHASE.get(kind, Phase.NEW)


def _declared_floor(snap: Snapshot, kind: Kind) -> Phase:
    """The declared phase, raised to the floor implied by work that has demonstrably started.

    A fact phase replaces the declaration label (`phase:ready` becomes `phase:in-review`); the floor
    keeps the declaration when the facts go away again, for example when the only PR is closed.
    A fact label can also be set by hand (violation V02), so only labels our own accounts wrote
    (`Snapshot.bot_phase_labels`) count, and a spec additionally needs a complete Definition of
    Ready. The legacy `wip` label (renamed by the label sync) counts as before.
    """
    declared = _declared_phase(snap, kind)
    floor = _STARTED_FLOOR.get(kind)
    if floor is None:
        return declared
    started = "wip" in snap.labels
    written = {p for p in _labelled(snap, Phase) if p.label in snap.bot_phase_labels}
    if written & _STARTED and (kind != Kind.SPEC or dor_status(snap.body)[0]):
        started = True
    return max(declared, floor, key=_PHASE_ORDER.index) if started else declared


def _resolution(snap: Snapshot) -> Resolution | None:
    found = _labelled(snap, Resolution)
    return found[0] if found else None


def _neighbours(snap: Snapshot, graph: Graph, type_: EdgeType) -> list[Snapshot]:
    """Snapshots at the end of `type_` edges; neighbours outside the fetched graph are skipped."""
    found = (graph.snapshots.get(e.target) for e in graph.edges_of(snap.number, type_))
    return [s for s in found if s is not None]


def _is_open(snap: Snapshot) -> bool:
    return snap.state == "open" and not snap.merged


# --- Waits ------------------------------------------------------------------------------------


def _latest_verdicts(reviews: tuple[Review, ...]) -> dict[str, Review]:
    """Each reviewer's latest approving, change-requesting or dismissed review (comments do not count)."""
    latest: dict[str, Review] = {}
    for review in reviews:
        if review.state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[review.user] = review
    return latest


def _approval_survives(snap: Snapshot, commit: str, cfg: Config) -> bool:
    """An approval holds on the head, or on an older commit followed only by exempt pushes.

    Only a push whose author is an allowlisted login with ``invalidates_approval: false`` is
    exempt: `Push.author` may be a spoofable git author name, so every other author invalidates.
    """
    if not commit:
        return False
    if commit == snap.head_sha:
        return True
    if snap.head_is_fork:
        # Fork branches are writable by their owner, who can commit under any author name, and
        # formatter-bot never pushes there: every push invalidates.
        return False
    # Known limitation: on same-repository branches a person with write access can still commit as
    # `formatter-bot` (unlinked e-mail, name fallback) and keep an approval; accepted as trusted-LAN
    # risk (SECURITY.md), because the real formatter-bot is identified by that name as well.
    shas = [push.sha for push in snap.pushes]
    if commit not in shas or shas[-1] != snap.head_sha:
        return False
    later = snap.pushes[shas.index(commit) + 1 :]
    return all(p.author in cfg.automation and not cfg.automation[p.author].invalidates_approval for p in later)


def _approved(snap: Snapshot, cfg: Config) -> bool:
    maintainer = snap.author_permission in cfg.maintainer_permissions
    for user, review in _latest_verdicts(snap.reviews).items():
        if review.state != "APPROVED" or not _approval_survives(snap, review.commit_id, cfg):
            continue
        if maintainer and user == OCT_SUPPORT:
            return True
        # Anyone can submit an APPROVED review on a public repository; only a reviewer whose
        # association grants write access counts (unknown or empty association fails closed).
        human = user and user != snap.author and user not in cfg.automation
        if not maintainer and human and review.author_association in _WRITE_ASSOCIATIONS:
            return True
    return False


_QUALITY_GATES = {"SonarCloud Code Analysis", "Gitar"}
_PASSED = {"success", "neutral", "skipped"}


def _pending(check: Check) -> bool:
    return check.status != "completed"


def _failed(check: Check) -> bool:
    return check.status == "completed" and check.conclusion not in _PASSED


def _findings(snap: Snapshot) -> bool:
    if snap.unresolved_threads > 0:  # -1 means unknown and is not a finding
        return True
    gitar = _latest_verdicts(snap.reviews).get(GITAR)
    if gitar is not None and gitar.state == "CHANGES_REQUESTED":
        return True
    return any(c.name in _QUALITY_GATES and _failed(c) for c in snap.checks)


def _ci(snap: Snapshot, cfg: Config) -> bool:
    gates = [c for c in snap.checks if c.name in cfg.gate_checks]
    return any(_pending(c) or (_failed(c) and c.name not in _QUALITY_GATES) for c in gates)


def _spec_ready(spec: Snapshot) -> bool:
    """Declared `ready` (with a complete checklist), or a fact phase written after `ready`.

    Fact phases never advance a spec below `ready` (see `_work_phase`), so an open PR cannot make
    its spec look ready and clear its own prerequisite. When the label history of the spec could not
    be read, readiness cannot be judged and the spec is not held against anybody (fail closed).
    """
    if spec.timeline_unknown:
        return True
    return _declared_floor(spec, Kind.SPEC) in _READY_OR_LATER


def spec_is_ready(spec: Snapshot) -> bool:
    """Public form of `_spec_ready` for the violation detectors."""
    return _spec_ready(spec)


def _prerequisite(snap: Snapshot, graph: Graph, cfg: Config) -> bool:
    blockers = _neighbours(snap, graph, EdgeType.STACKED_ON) + _neighbours(snap, graph, EdgeType.DEPENDS_ON)
    if any(_is_open(s) for s in blockers):
        return True
    targets = _neighbours(snap, graph, EdgeType.IMPLEMENTS) if snap.is_pr else []
    return any(_is_open(t) and detect_kind(t, cfg) == Kind.SPEC and not _spec_ready(t) for t in targets)


def _hardware(snap: Snapshot, graph: Graph) -> bool:
    """Open `verifies` test plans on the artifact (and, for an issue, on its PRs) decide.

    Without any known test plan the declared label stands until `/oct verified` removes it.
    """
    owners = [snap] + ([] if snap.is_pr else _neighbours(snap, graph, EdgeType.IMPLEMENTED_BY))
    plans = [p for owner in owners for p in _neighbours(owner, graph, EdgeType.VERIFIED_BY)]
    if plans:
        return any(_is_open(p) for p in plans)
    return Wait.HARDWARE_TEST.label in snap.labels


def _open_waits(snap: Snapshot, graph: Graph, cfg: Config) -> set[Wait]:
    waits = set(_labelled(snap, Wait)) & _DECLARED_WAITS
    if _prerequisite(snap, graph, cfg):
        waits.add(Wait.PREREQUISITE)
    if _hardware(snap, graph):
        waits.add(Wait.HARDWARE_TEST)
    return waits


# --- Phases -----------------------------------------------------------------------------------


def _derive_pr(snap: Snapshot, graph: Graph, cfg: Config) -> Derived:
    if snap.merged:
        return Derived(Phase.MERGED, frozenset({Wait.HARDWARE_TEST} if _hardware(snap, graph) else ()), None)
    if snap.state != "open":
        return Derived(Phase.CLOSED, frozenset(), _resolution(snap))
    waits = _open_waits(snap, graph, cfg)
    if not snap.draft and not _approved(snap, cfg):
        waits.add(Wait.MAINTAINER)
    if _findings(snap):
        waits.add(Wait.FINDINGS)
    if _ci(snap, cfg):
        waits.add(Wait.CI)
    return Derived(Phase.DRAFT if snap.draft else Phase.IN_REVIEW, frozenset(waits), None)


def _work_phase(snap: Snapshot, kind: Kind, graph: Graph) -> Phase:
    """Spec, bug and feature request: linked PRs are facts, otherwise the declared phase."""
    hardware = _hardware(snap, graph)
    if snap.state != "open":
        if _resolution(snap):
            return Phase.CLOSED
        return Phase.VERIFICATION if hardware else Phase.DONE
    floor = _declared_floor(snap, kind)
    if kind == Kind.SPEC and floor not in _READY_OR_LATER:
        return floor  # PRs for a spec that is not ready do not advance it (V06 reports them)
    parts = [p for p in _neighbours(snap, graph, EdgeType.IMPLEMENTED_BY) if p.is_pr]
    open_parts = [p for p in parts if _is_open(p)]
    if any(not p.draft for p in open_parts):
        return Phase.IN_REVIEW
    if open_parts or "wip" in snap.labels:
        return Phase.IN_PROGRESS
    if any(p.merged for p in parts):
        # Ruling: an open issue whose known parts are all merged may still get more parts.
        return Phase.VERIFICATION if hardware else Phase.IN_PROGRESS
    return floor


def _mirrored(snap: Snapshot, graph: Graph, cfg: Config) -> tuple[Phase, Resolution | None] | None:
    """A feature request with a spec mirrors the least advanced live spec; all dropped: superseded."""
    specs = [s for s in _neighbours(snap, graph, EdgeType.SPECIFIED_BY) if detect_kind(s, cfg) == Kind.SPEC]
    if not specs or (snap.state != "open" and _resolution(snap)):
        return None
    phases = [(graph.derived.get(s.number) or _derive_known(s, graph, cfg, Kind.SPEC)).phase for s in specs]
    live = [p for p in phases if p != Phase.CLOSED]
    if not live:
        return Phase.CLOSED, Resolution.SUPERSEDED
    return min(live, key=_PHASE_ORDER.index), None


def _simple_phase(snap: Snapshot, kind: Kind, graph: Graph) -> Phase:
    """Tracking issues, test plans and discussions."""
    if kind == Kind.DISCUSSION:
        if _neighbours(snap, graph, EdgeType.SPECIFIED_BY) or _neighbours(snap, graph, EdgeType.SPAWNED):
            return Phase.SPECIFIED
        declared = _declared_phase(snap, kind)
        if snap.state != "open":
            return Phase.ANSWERED if declared == Phase.ANSWERED else Phase.CLOSED
        return declared
    if snap.state != "open":
        return Phase.CLOSED if _resolution(snap) else Phase.DONE
    if kind == Kind.TRACKING:
        children = [e.target for e in graph.edges_of(snap.number, EdgeType.TRACKS)]
        if not children:
            return Phase.NEW
        known = graph.snapshots
        return Phase.IN_PROGRESS if any(c not in known or _is_open(known[c]) for c in children) else Phase.DONE
    return _declared_phase(snap, kind)


def derive(snap: Snapshot, graph: Graph, cfg: Config, kind: Kind | None = None) -> Derived | None:
    """Phase, waits and resolution of one artifact (design section 6); pure.

    `kind` is detected from the snapshot unless given (discussions are never detected).
    Fact-owned labels on the artifact are ignored and recomputed; declarations are validated.
    Returns ``None`` for an announcement (content by allowlisted automation): it has no phase,
    no waits and no block, and callers write nothing for it.
    """
    kind = kind or detect_kind(snap, cfg)
    if kind == Kind.ANNOUNCEMENT:
        return None
    return _derive_known(snap, graph, cfg, kind)


def _derive_known(snap: Snapshot, graph: Graph, cfg: Config, kind: Kind) -> Derived:
    if kind in (Kind.PULL_REQUEST, Kind.DEPENDENCY_PR, Kind.DOCS_PR):
        return _derive_pr(snap, graph, cfg)
    resolution: Resolution | None = None
    mirrored = _mirrored(snap, graph, cfg) if kind == Kind.FEATURE_REQUEST else None
    if mirrored is not None:
        phase, resolution = mirrored
    elif kind in (Kind.SPEC, Kind.BUG, Kind.FEATURE_REQUEST):
        phase = _work_phase(snap, kind, graph)
    else:
        phase = _simple_phase(snap, kind, graph)
    if phase == Phase.CLOSED:
        return Derived(phase, frozenset(), resolution or _resolution(snap))
    if snap.state != "open" or phase == Phase.DONE:
        return Derived(phase, frozenset({Wait.HARDWARE_TEST} if phase == Phase.VERIFICATION else ()), None)
    return Derived(phase, frozenset(_open_waits(snap, graph, cfg)), None)
