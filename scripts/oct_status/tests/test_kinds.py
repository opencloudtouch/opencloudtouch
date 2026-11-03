from __future__ import annotations

from pathlib import Path

import pytest

from oct_status.api import GitHubApi
from oct_status.config import load_config
from oct_status.facts import fetch_snapshot
from oct_status.model import Kind
from oct_status.rules import detect_kind

from .conftest import FixtureTransport, make_snapshot

CFG = load_config(Path(__file__).parent.parent / "config.yml")


@pytest.mark.parametrize(
    ("number", "kind"),
    [
        (537, Kind.SPEC),
        (575, Kind.BUG),
        (577, Kind.BUG),
        (498, Kind.DEPENDENCY_PR),
        (574, Kind.PULL_REQUEST),
    ],
)
async def test_detect_kind_fixtures(number, kind):
    api = GitHubApi("t", "opencloudtouch/opencloudtouch", transport=FixtureTransport([number]))
    snap = await fetch_snapshot(api, number, use_graphql=False)
    assert detect_kind(snap, CFG) == kind


@pytest.mark.parametrize(
    ("overrides", "kind"),
    [
        ({"title": "[Tracking] Sleep timer"}, Kind.TRACKING),
        ({"title": "[Test] Sleep timer on hardware"}, Kind.TEST_PLAN),
        ({"title": "bump x", "is_pr": True, "author": "dependabot[bot]"}, Kind.DEPENDENCY_PR),
        ({"title": "docs: update guide", "is_pr": True}, Kind.DOCS_PR),
        ({"title": "ci(deps): pin action", "is_pr": True}, Kind.DOCS_PR),
        ({"title": "chore!: drop thing", "is_pr": True}, Kind.DOCS_PR),
        ({"title": "feat(api): add x", "is_pr": True}, Kind.PULL_REQUEST),
        ({"title": "no convention", "is_pr": True}, Kind.PULL_REQUEST),
        ({"title": "x", "labels": frozenset({"bug", "spec"})}, Kind.SPEC),
        ({"title": "x", "labels": frozenset({"enhancement"})}, Kind.FEATURE_REQUEST),
        ({"title": "x", "labels": frozenset({"support"})}, Kind.BUG),
        ({"title": "x", "author": "github-actions[bot]"}, Kind.ANNOUNCEMENT),
        ({"title": "x", "author": "github-actions[bot]", "is_pr": True}, Kind.ANNOUNCEMENT),
        ({"title": "x", "author": "someone"}, Kind.FEATURE_REQUEST),
    ],
)
def test_detect_kind(overrides, kind):
    assert detect_kind(make_snapshot(**overrides), CFG) == kind
