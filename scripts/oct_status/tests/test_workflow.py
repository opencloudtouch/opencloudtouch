"""The workflow keeps write mode behind the OCT_STATUS_WRITE variable (maintainer go/no-go, MA-5)."""

from __future__ import annotations

import re
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
        "statuses": "write",  # the commit status `oct-status` is the required check
        "contents": "read",
    }
    others = {name: j for name, j in _jobs().items() if name != "status-write"}
    assert all("statuses" not in (j.get("permissions") or {}) for j in others.values())
    assert "actions: write" not in WORKFLOW.read_text(encoding="utf-8")
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "commit STATUS context `oct-status`" in text
    assert "github.event.check_suite.pull_requests[0].number" in text  # check suites join the PR's group
    # The job token (with `statuses: write`) reaches the write job's steps; BOT_PAT gets no new scope.
    assert all("GITHUB_TOKEN" in (s.get("env") or {}) for s in job["steps"] if "python -m" in s.get("run", ""))
    event = next(s for s in job["steps"] if s.get("name") == "Process event")
    assert "--dry-run" not in event["run"] and "BOT_PAT" in event["env"]


def test_no_job_can_satisfy_a_required_check_named_oct_status():
    """Only the commit status context `oct-status` may satisfy the required check (Task 20)."""
    jobs = _jobs()
    assert "oct-status" not in jobs
    assert all(j.get("name") != "oct-status" for j in jobs.values())
    assert jobs["oct-status-report"]["name"] == "oct-status-report"


def test_check_blocks_only_in_write_mode_and_backfill_defaults_to_dry_run():
    jobs = _jobs()
    check = next(s for s in jobs["oct-status-report"]["steps"] if "--check" in s.get("run", ""))
    assert check["continue-on-error"] == "${{ vars.OCT_STATUS_WRITE != 'true' }}"
    assert set(jobs["oct-status-report"]["needs"]) == {"status", "status-write"}
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


def _raw() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_ci_completion_triggers_a_run():
    on = _raw()[True]  # YAML 1.1 reads the key `on` as True
    assert on["workflow_run"] == {"workflows": ["CI"], "types": ["completed"]}
    # GitHub Actions has no pull_request_review_thread trigger (webhook only; actionlint rejects it).
    assert "pull_request_review_thread" not in on
    ci = yaml.safe_load((WORKFLOW.parent / "ci.yml").read_text(encoding="utf-8"))
    assert ci["name"] == "CI"  # workflow_run matches the workflow by its name


def _group(event: dict, run_id: str = "777") -> str:
    """Evaluate the concurrency group for an event payload (the `||` / `&&` / format subset it uses)."""
    expr = re.fullmatch(r"oct-status-\$\{\{ (.*) \}\}", _raw()["concurrency"]["group"])
    assert expr, "the group is one expression after a fixed prefix"

    def value(path: str) -> object:
        if path == "github.run_id":
            return run_id
        node: object = event
        for part in re.findall(r"[a-z_]+|\[\d+\]", path.removeprefix("github.event.")):
            if part.startswith("["):
                index = int(part[1:-1])
                node = node[index] if isinstance(node, list) and len(node) > index else None
            else:
                node = node.get(part) if isinstance(node, dict) else None
        return node

    for operand in (o.strip() for o in expr[1].split("||")):
        guarded = re.fullmatch(r"\((github\.event\.[\w.]+) && format\('([\w-]*)\{0\}', \1\)\)", operand)
        if guarded:
            result = value(guarded[1])
            result = f"{guarded[2]}{result}" if result else None
        else:
            assert re.fullmatch(r"github\.[\w.\[\]]+", operand), operand
            result = value(operand)
        if result:
            return f"oct-status-{result}"
    raise AssertionError("github.run_id is always set")


def test_concurrency_group_per_artifact_and_per_commit_for_forks():
    sha = "c" * 40
    assert _group({"issue": {"number": 5}}) == "oct-status-5"
    assert _group({"pull_request": {"number": 6}}) == "oct-status-6"
    assert _group({"check_suite": {"pull_requests": [{"number": 7}], "head_sha": sha}}) == "oct-status-7"
    assert _group({"workflow_run": {"pull_requests": [{"number": 8}], "head_sha": sha}}) == "oct-status-8"
    # M10: a fork's check suite or CI run names no pull request; it serialises per commit, not per run.
    assert _group({"check_suite": {"pull_requests": [], "head_sha": sha}}) == f"oct-status-sha-{sha}"
    assert _group({"workflow_run": {"pull_requests": [], "head_sha": sha}}) == f"oct-status-sha-{sha}"
    assert _group({}) == "oct-status-777"  # schedule and manual runs


def test_every_job_checks_out_the_default_branch_and_reads_the_payload_file():
    text = WORKFLOW.read_text(encoding="utf-8")
    for name, job in _jobs().items():
        for step in job["steps"]:
            if "actions/checkout" in step.get("uses", ""):
                assert step["with"] == {
                    "ref": "${{ github.event.repository.default_branch }}",
                    "persist-credentials": False,
                }, name
            assert "github.event." not in step.get("run", ""), name  # payload only via $GITHUB_EVENT_PATH
    assert "workflow_run.head_branch" not in text and "head_commit" not in text
