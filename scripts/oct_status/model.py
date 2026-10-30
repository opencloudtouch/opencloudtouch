"""Plain data types shared by all oct_status components."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Phase(StrEnum):
    NEW = "new"
    DRAFT = "draft"
    TRIAGED = "triaged"
    SPEC_REVIEW = "spec-review"
    SPEC_REWORK = "spec-rework"
    CONFIRMED = "confirmed"
    READY = "ready"
    IN_PROGRESS = "in-progress"
    IN_REVIEW = "in-review"
    VERIFICATION = "verification"
    DONE = "done"
    MERGED = "merged"
    CLOSED = "closed"
    OPEN = "open"
    NEEDS_SPEC = "needs-spec"
    SPECIFIED = "specified"
    ANSWERED = "answered"

    @property
    def label(self) -> str:
        return f"phase:{self.value}"


class Wait(StrEnum):
    MAINTAINER = "maintainer"
    FINDINGS = "findings"
    CI = "ci"
    PREREQUISITE = "prerequisite"
    HARDWARE_TEST = "hardware-test"
    SPEC_FIX = "spec-fix"
    REPORTER = "reporter"
    DESIGNER = "designer"

    @property
    def label(self) -> str:
        return f"wait:{self.value}"


class Resolution(StrEnum):
    DUPLICATE = "duplicate"
    WONTFIX = "wontfix"
    INVALID = "invalid"
    NOT_REPRODUCIBLE = "not-reproducible"
    WORKS_AS_DESIGNED = "works-as-designed"
    SUPERSEDED = "superseded"
    ABANDONED = "abandoned"

    @property
    def label(self) -> str:
        return f"resolution:{self.value}"


class Kind(StrEnum):
    SPEC = "spec"
    BUG = "bug"
    FEATURE_REQUEST = "feature-request"
    TRACKING = "tracking"
    TEST_PLAN = "test-plan"
    PULL_REQUEST = "pull-request"
    DEPENDENCY_PR = "dependency-pr"
    DOCS_PR = "docs-pr"
    DISCUSSION = "discussion"
    ANNOUNCEMENT = "announcement"


class EdgeType(StrEnum):
    IMPLEMENTS = "implements"
    IMPLEMENTED_BY = "implemented-by"
    STACKED_ON = "stacked-on"
    STACKED_BY = "stacked-by"
    DEPENDS_ON = "depends-on"
    BLOCKS = "blocks"
    VERIFIES = "verifies"
    VERIFIED_BY = "verified-by"
    SPECIFIED_BY = "specified-by"
    SPECIFIES = "specifies"
    ORIGIN = "origin"
    SPAWNED = "spawned"
    TRACKS = "tracks"
    TRACKED_BY = "tracked-by"
    SUPERSEDED_BY = "superseded-by"
    SUPERSEDES = "supersedes"
    RELATED = "related"
    FOLLOW_UP = "follow-up"


@dataclass(frozen=True)
class Review:
    user: str
    state: str
    commit_id: str
    author_association: str = ""


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    conclusion: str | None
    app: str


@dataclass(frozen=True)
class Push:
    sha: str
    author: str
    paths: tuple[str, ...]
    committer: str = ""  # committer login (GitHub API linked account), "" when unknown


@dataclass(frozen=True)
class Edge:
    type: EdgeType
    source: int
    target: int
    origin: Literal["native", "prose"]


@dataclass(frozen=True)
class Snapshot:
    number: int
    is_pr: bool
    title: str
    body: str
    state: str
    merged: bool
    draft: bool
    author: str
    author_permission: str | None
    labels: frozenset[str]
    base_ref: str
    head_ref: str
    head_sha: str
    reviews: tuple[Review, ...]
    unresolved_threads: int
    checks: tuple[Check, ...]
    closing_refs: tuple[int, ...]
    sub_issues: tuple[int, ...]
    blocked_by: tuple[int, ...]
    pushes: tuple[Push, ...]
    stack_drift: int | None
    head_is_fork: bool = False
    no_spec_reason: str | None = None  # reason of a `/oct no-spec` by the PR author (design section 11)
    author_association: str = ""  # GitHub's association of the author (OWNER, CONTRIBUTOR, FIRST_TIME_CONTRIBUTOR, ...)
    # Current `phase:*` labels whose latest LabeledEvent was written by our own accounts. Only these fact
    # labels are trusted (rules._declared_floor); a label set by hand is violation V02.
    bot_phase_labels: frozenset[str] = frozenset()
    timeline_unknown: bool = False  # the label timeline could not be read (nothing is trusted then)
    # Head SHA up to which a maintainer acknowledged automation pushes to protected paths (`/oct accept-paths`),
    # read from the guide comment's data; "" when nothing was acknowledged.
    paths_accepted: str = ""
    # Head SHA for which the guide last listed unacknowledged protected-path changes; `/oct accept-paths`
    # acknowledges up to this commit only (what the maintainer saw), "" when none was listed.
    paths_pending: str = ""


@dataclass(frozen=True)
class Derived:
    phase: Phase
    waits: frozenset[Wait]
    resolution: Resolution | None


@dataclass
class Graph:
    edges: list[Edge]
    snapshots: dict[int, Snapshot]
    derived: dict[int, Derived]

    def edges_of(self, number: int, type: EdgeType | None = None) -> list[Edge]:
        """Edges whose source is `number`, optionally restricted to one type."""
        return [e for e in self.edges if e.source == number and (type is None or e.type == type)]
