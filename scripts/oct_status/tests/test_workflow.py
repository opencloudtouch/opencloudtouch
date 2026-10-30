"""The workflow keeps write mode behind the OCT_STATUS_WRITE variable (maintainer go/no-go, MA-5)."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "oct-status.yml"
GATE = "vars.OCT_STATUS_WRITE"


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _runs(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def test_shadow_job_never_writes():
    job = _jobs()["status"]
    assert f"{GATE} != 'true'" in job["if"]
    assert all(v == "read" for v in job["permissions"].values())
    commands = [line for line in _runs(job).splitlines() if "python -m oct_status" in line]
    assert commands and all("--dry-run" in line for line in commands)
    assert "BOT_PAT" not in str(job)


def test_write_job_is_gated_and_least_privileged():
    job = _jobs()["status-write"]
    assert f"{GATE} == 'true'" in job["if"]
    assert job["permissions"] == {
        "issues": "write",
        "pull-requests": "write",
        "checks": "read",
        "actions": "read",
        "contents": "read",
    }
    event = next(s for s in job["steps"] if s.get("name") == "Process event")
    assert "--dry-run" not in event["run"] and "BOT_PAT" in event["env"]


def test_check_blocks_only_in_write_mode_and_backfill_defaults_to_dry_run():
    jobs = _jobs()
    check = next(s for s in jobs["oct-status"]["steps"] if "--check" in s.get("run", ""))
    assert check["continue-on-error"] == "${{ vars.OCT_STATUS_WRITE != 'true' }}"
    assert set(jobs["oct-status"]["needs"]) == {"status", "status-write"}
    raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    inputs = raw[True]["workflow_dispatch"]["inputs"]  # YAML 1.1 reads the key `on` as True
    assert inputs["dry_run"]["default"] is True and inputs["limit"] == {
        "description": "Artifacts per backfill run",
        "type": "number",
        "default": 25,
    }
    assert "backfill" in inputs["mode"]["options"]
    backfill = jobs["backfill"]
    assert "--dry-run" in _runs(backfill) and "--limit" in _runs(backfill)
    assert "discussions" not in str(jobs)
