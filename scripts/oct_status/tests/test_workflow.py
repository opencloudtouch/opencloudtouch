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
        "actions": "write",  # re-runs the failed check; no other job may write Actions
        "contents": "read",
    }
    others = {name: j for name, j in _jobs().items() if name != "status-write"}
    assert all((j.get("permissions") or {}).get("actions") != "write" for j in others.values())
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
    dry = jobs["backfill"]
    assert "inputs.dry_run" in dry["if"] and all(v == "read" for v in dry["permissions"].values())
    assert "BOT_PAT" not in str(dry) and "--dry-run" in _runs(dry) and "--limit" in _runs(dry)
    assert not [s for s in dry["steps"] if "cache/save" in s.get("uses", "")]
    refused = jobs["backfill-refused"]
    assert "!inputs.dry_run" in refused["if"] and f"{GATE} != 'true'" in refused["if"]
    assert "exit 1" in _runs(refused)
    write = jobs["backfill-write"]
    assert "!inputs.dry_run" in write["if"] and f"{GATE} == 'true'" in write["if"]
    assert "--dry-run" not in _runs(write) and "BOT_PAT" in str(write)
    assert "discussions" not in str(jobs)
