"""Kind detection and (Task 8) derivation of phase, waits and resolution."""

from __future__ import annotations

import re

from .config import Config
from .model import Kind, Snapshot

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
        if match and match.group(1).lower() in _CHORE_TYPES:
            return Kind.DOCS_PR
        return Kind.PULL_REQUEST
    if "spec" in snap.labels:
        return Kind.SPEC
    if snap.labels & {"bug", "support"}:
        return Kind.BUG
    return Kind.FEATURE_REQUEST
