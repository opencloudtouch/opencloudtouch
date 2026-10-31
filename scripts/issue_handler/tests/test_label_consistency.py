"""Consistency checks between handler, workflows, Dependabot and the status system config."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
EXISTING_REPO_LABELS = {"dependencies", "github_actions"}


def _label_names() -> set[str]:
    data = yaml.safe_load((REPO / "scripts/oct_status/labels.yml").read_text())
    return {entry["name"] for entry in data["labels"]}


def test_spotlight_exclusions_are_subset_of_actor_config() -> None:
    workflow = (REPO / ".github/workflows/monthly-community-spotlight.yml").read_text()
    match = re.search(r"EXCLUDE_LOGINS='(\[.*?\])'", workflow)
    assert match, "EXCLUDE_LOGINS not found"
    import json

    logins = json.loads(match.group(1))
    config = yaml.safe_load((REPO / "scripts/oct_status/config.yml").read_text())
    # GraphQL author logins omit the "[bot]" suffix that REST logins carry.
    known = {key.removesuffix("[bot]") for key in config["automation"]} | {"scheilch"}
    assert set(logins) <= known, f"missing from actor config: {set(logins) - known}"


def test_dependabot_labels_exist() -> None:
    data = yaml.safe_load((REPO / ".github/dependabot.yml").read_text())
    allowed = _label_names() | EXISTING_REPO_LABELS
    for update in data["updates"]:
        assert set(update.get("labels", [])) <= allowed, update["package-ecosystem"]
        assert "user" not in update.get("reviewers", [])
        assert "user" not in update.get("assignees", [])


def test_issue_handler_skips_status_bot_events() -> None:
    data = yaml.safe_load((REPO / ".github/workflows/issue-handler.yml").read_text())
    condition = data["jobs"]["triage"]["if"]
    assert "github.event.sender.login != 'oct-support'" in condition
    assert "github.event.comment.user.login != 'scheilch'" in condition
