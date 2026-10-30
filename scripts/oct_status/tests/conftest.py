"""Shared test helpers for oct_status."""

from __future__ import annotations

from typing import Any

from oct_status.model import Snapshot


def make_snapshot(**overrides: Any) -> Snapshot:
    """Build a Snapshot with neutral defaults; override any field by keyword."""
    values: dict[str, Any] = {
        "number": 1,
        "is_pr": False,
        "title": "",
        "body": "",
        "state": "open",
        "merged": False,
        "draft": False,
        "author": "someone",
        "author_permission": None,
        "labels": frozenset(),
        "base_ref": "",
        "head_ref": "",
        "head_sha": "",
        "reviews": (),
        "unresolved_threads": 0,
        "checks": (),
        "closing_refs": (),
        "sub_issues": (),
        "blocked_by": (),
        "pushes": (),
        "stack_drift": None,
        "head_is_fork": False,
    }
    values.update(overrides)
    return Snapshot(**values)
