"""Next steps and the guide comment (design section 5a).

The guide never starts with the word "gitar" and never mentions the bot account: every piece of
text that goes in is passed through ``_safe``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace

from .config import Config
from .model import Derived, EdgeType, Graph, Snapshot, Wait
from .render import neutralise
from .rules import detect_kind, dor_status, legal_transitions

MAX_STEPS = 5
WORKFLOW = "https://github.com/opencloudtouch/opencloudtouch/blob/main/docs/WORKFLOW.md"
RESOLVED = "[resolved] "
_WAIT_ORDER = list(Wait)
_BOT = re.compile(r"@?gitar-bot(\[bot\])?", re.IGNORECASE)
_LEADING = re.compile(r"^\s*@?gitar", re.IGNORECASE)


@dataclass(frozen=True)
class Step:
    actor: str
    text: str
    command: str | None = None


def _safe(text: str) -> str:
    text = neutralise(_BOT.sub("the review bot", text))
    return f"Review by {text.lstrip()}" if _LEADING.match(text) else text


def _blockers(snap: Snapshot, graph: Graph | None) -> list[str]:
    if graph is not None:
        numbers = sorted(
            {
                e.target
                for t in (EdgeType.STACKED_ON, EdgeType.DEPENDS_ON)
                for e in graph.edges_of(snap.number, t)
                if (s := graph.snapshots.get(e.target)) is None or (s.state == "open" and not s.merged)
            }
        )
        return [f"#{n}" for n in numbers]
    names = [f"#{n}" for n in sorted(snap.blocked_by)]
    if snap.is_pr and snap.base_ref and snap.base_ref != "main":
        names.append(f"stack parent branch `{snap.base_ref}`")
    return names


def _wait_step(wait: Wait, snap: Snapshot, graph: Graph | None) -> Step:
    if wait == Wait.MAINTAINER:
        return Step("author", "Request the review by oct-support; its approval clears wait:maintainer", "/oct approve")
    if wait == Wait.FINDINGS:
        n = snap.unresolved_threads
        return Step(
            "author",
            f"Resolve the {n} open review thread{'s' if n != 1 else ''}" if n else "Address the open review findings",
        )
    if wait == Wait.CI:
        return Step("author", "Fix the failing or pending checks")
    if wait == Wait.PREREQUISITE:
        blockers = ", ".join(_blockers(snap, graph)) or "the blocking artifacts"
        return Step("author", f"Wait for {blockers} to be merged or done")
    if wait == Wait.HARDWARE_TEST:
        return Step("maintainer", "Verify on a real device and record the result", "/oct verified <device or note>")
    if wait == Wait.SPEC_FIX:
        return Step("author", "Address the rework reason, then request the review again")
    if wait == Wait.REPORTER:
        return Step("reporter", "Provide the requested information")
    return Step("designer", "Provide the design")


_READY = '/oct ready --reviewer <login or "independent-review">'
_COMMANDS = {
    "review": "/oct review",
    "rework": "/oct rework <reason>",
    "ready": _READY,
    "triage": "/oct triage",
    "confirm": "/oct confirm",
}
_WAIT_COMMANDS = {Wait.MAINTAINER: "/oct approve", Wait.HARDWARE_TEST: "/oct verified <device or note>"}


def valid_commands(snap: Snapshot, derived: Derived, cfg: Config) -> list[str]:
    """Every command legal now: state-machine transitions plus those that clear a wait."""
    commands = [_COMMANDS[c] for c in legal_transitions(detect_kind(snap, cfg), derived.phase)]
    commands += [_WAIT_COMMANDS[w] for w in sorted(derived.waits, key=_WAIT_ORDER.index) if w in _WAIT_COMMANDS]
    return commands


def _transition_step(command: str, body: str) -> Step:
    if command in ("review", "ready"):
        complete, open_items = dor_status(body)
        if not complete:
            items = "; ".join(open_items)
            return Step("author", f"Before /oct {command}, complete the Definition of Ready. Open: {items}")
        if command == "ready":
            return Step("reviewer", "Mark the spec ready after the review", _READY)
        return Step("author", "Request the specification review", "/oct review")
    if command == "rework":
        return Step("reviewer", "Send the spec back for rework", "/oct rework <reason>")
    return Step("maintainer", f"Record the decision: {command}", f"/oct {command}")


def next_steps(snap: Snapshot, derived: Derived, cfg: Config, graph: Graph | None = None) -> list[Step]:
    """At most five steps: first what clears each wait, then the legal transitions."""
    steps = [_wait_step(w, snap, graph) for w in sorted(derived.waits, key=_WAIT_ORDER.index)]
    for command in legal_transitions(detect_kind(snap, cfg), derived.phase):
        steps.append(_transition_step(command, snap.body))
    return steps[:MAX_STEPS]


def _section(title: str, lines: list[str]) -> list[str]:
    return [f"### {title}", "", *lines, ""]


def _details(summary: str, lines: list[str]) -> list[str]:
    return ["<details>", f"<summary>{summary}</summary>", "", *lines, "", "</details>", ""]


def render_guide(
    snap: Snapshot,
    derived: Derived,
    steps: list[Step],
    notices: list[str],
    history: list[str],
    cfg: Config | None = None,
) -> str:
    """The guide comment; `history` and `notices` are newest first, resolved notices start with ``[resolved] ``."""
    out = ["<!-- oct-next:v1 -->", ""]
    out += _section("Last action", [_safe(history[0]) if history else "-"])
    waits = ", ".join(w.value for w in sorted(derived.waits, key=_WAIT_ORDER.index)) or "nothing"
    anchor = derived.phase.value
    out += _section("You are here", [f"Phase **{anchor}**, waiting on: {waits}. [Workflow guide]({WORKFLOW}#{anchor})"])
    lines: list[str] = []
    for index, step in enumerate(steps[:MAX_STEPS], 1):
        lines.append(f"{index}. **{step.actor}**: {_safe(step.text)}")
        if step.command:
            lines += ["   ```", f"   {step.command}", "   ```"]
    out += _section("Next steps", lines or ["Nothing to do."])
    if cfg is not None:  # independent of the five-step cap
        commands = list(dict.fromkeys(valid_commands(snap, derived, cfg)))
    else:
        commands = [c for c in dict.fromkeys(s.command for s in steps) if c]
    out += _section("Commands valid now", [f"- `{c}`" for c in commands] or ["None."])
    open_notes = [_safe(n) for n in notices if not n.startswith(RESOLVED)]
    done_notes = [_safe(n[len(RESOLVED) :]) for n in notices if n.startswith(RESOLVED)]
    note_lines = [f"- {n}" for n in open_notes] or ["None."]
    out += _section("Notices", note_lines)
    if done_notes:
        out += _details(f"Resolved notices ({len(done_notes)})", [f"- {n}" for n in done_notes])
    out += ["### History", ""]
    out += _details("Last five actions", [f"- {_safe(h)}" for h in history[:5]] or ["-"])
    data = {
        "phase": derived.phase.value,
        "waits": sorted(w.value for w in derived.waits),
        "next": [asdict(replace(s, text=_safe(s.text))) for s in steps[:MAX_STEPS]],
    }
    payload = json.dumps(data, sort_keys=True).replace("--", "\\u002d\\u002d")
    out.append(f"<!-- oct-next-data {payload} -->")
    return "\n".join(out) + "\n"
