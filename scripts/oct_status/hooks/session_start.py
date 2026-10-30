"""SessionStart hook: tells the session the status rules and, when known, the state of its artifact.

The artifact is determined only when that is unambiguous: a branch named ``type/<n>-...`` (or
``type/<n>``) names issue or pull request ``<n>``; otherwise the single open pull request whose head is
the current branch (REST, 5 s timeout). Its status block and the guide comment's data block are
injected; otherwise only the static rules. The hook is advisory and never fails the session start: any
error still prints the static rules and exits 0.

Only the standard library and stdlib-only modules of this package may be imported here.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # run as a script: make `oct_status` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

MAX_CONTEXT = 9_000  # Claude Code keeps 10,000 characters inline
_BRANCH_NUMBER = re.compile(r"^[a-z]+/(\d+)(?:-|$)")

RULES = """\
OCT status system (docs/WORKFLOW.md, section "Agents and subagents"; CLAUDE.md "Status system"):
- Never edit the oct-status block (<!-- oct-status:v1 ... --> ... <!-- /oct-status -->) or the phase:, wait: \
and resolution: labels. Change the state with /oct commands in a comment (for example /oct review, \
/oct ready --reviewer LOGIN, /oct approve, /oct no-spec REASON).
- Never edit or reply to the guide comment (<!-- oct-next:v1 -->). Its <!-- oct-next-data {...} --> block \
lists the phase, the waits and the next steps.
- A pull request names its spec with "Part of #n" (or "Closes #n" when it completes the spec), keeps every \
section and item of .github/pull_request_template.md (mark items that do not apply as n/a with a reason) \
and is opened only for a spec at phase:ready or later; with an unmerged prerequisite it is stacked on the \
prerequisite's branch.
- Hooks in .claude/settings.json guard GitHub writes, also for subagents: description writes through the \
GitHub MCP tools get the current status block spliced in, body and comment writes get the marker \
<!-- oct-src:1 -->, status label changes are denied, pull request creation is gated, and \
gh issue/pr edit|create|comment with a body or status labels and direct API writes to issues or pull \
requests are denied with the allowed route. A denial quotes the next steps; follow them.
- Start every subagent prompt with: "Follow the Status system section of CLAUDE.md: do not edit the \
oct-status block or phase/wait/resolution labels; use /oct commands."
"""


def _artifact(branch: str | None, api: Any) -> tuple[int | None, str]:
    if not branch:
        return None, ""
    if match := _BRANCH_NUMBER.match(branch):
        return int(match[1]), f"branch {branch}"
    if api is None:
        return None, ""
    number = api.open_pull_for_head(branch)
    return (number, f"the open pull request of branch {branch}") if number else (None, "")


def build_context(env: Mapping[str, str], event: Mapping[str, Any], api_for: Callable[[str, str], Any]) -> str:
    from oct_status.hooks import guard, rest

    project = rest.project_dir(env, event)
    repo = rest.origin_repo(project)
    api = api_for(*repo) if repo else None
    number, source = _artifact(rest.current_branch(project), api)
    if number is None or api is None:
        return guard.safe(RULES)
    try:
        issue = api.issue(number)
        comment = api.guide_comment(number)
    except rest.RestError:
        return guard.safe(f"{RULES}\nArtifact #{number} (from {source}): its status could not be read.")
    guide_body = (comment or {}).get("body") or ""
    block = guard.extract_block(issue.get("body") or "") or guard.extract_block(guide_body)
    data = guard.parse_guide_data(guide_body)
    lines = [
        RULES,
        f"Artifact this session works on: #{number} (from {source}): {guard._plain(issue.get('title', ''))}",
    ]
    lines.append(guard.next_steps(data, number) or "It has no guide comment data yet.")
    if data is not None:
        lines.append("Guide data: " + json.dumps(data, ensure_ascii=False, sort_keys=True)[:3000])
    lines.append("Current status block:\n" + block if block else "It has no status block yet.")
    return guard.safe("\n".join(lines))[:MAX_CONTEXT]


def main(
    stdin: Any = None,
    stdout: Any = None,
    env: Mapping[str, str] | None = None,
    api_for: Callable[[str, str], Any] | None = None,
) -> int:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    env = os.environ if env is None else env
    try:
        try:
            event = json.loads(stdin.read() or "{}")
        except ValueError:
            event = {}
        if api_for is None:  # pragma: no cover - real network
            from oct_status.hooks import rest

            def api_for(owner: str, repo: str) -> Any:
                return rest.Rest(owner, repo, rest.find_token(env))

        text = build_context(env, event if isinstance(event, dict) else {}, api_for)
    except Exception:  # noqa: BLE001 - advisory: never fail the session start
        text = RULES
    stdout.write(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
