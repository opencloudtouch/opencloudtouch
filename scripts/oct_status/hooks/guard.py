"""PreToolUse guard for agents and subagents (design section 8, layer 1).

``decide`` is a pure function of the tool call and the current state of the artifact. The wrapper
(``main``) reads the hook event from stdin, fetches that state through REST (at most 5 s per request
within an overall budget of 40 s) and answers in the hook JSON format on stdout.

- Body writes (issue and pull request descriptions) get the current status block spliced in through
  ``updatedInput``; if the block cannot be read, the write is denied (fail closed) and the agent is
  pointed to a comment instead.
- Changes to ``phase:``, ``wait:`` and ``resolution:`` labels are denied with the ``/oct`` alternative.
- Pull request creation is gated: spec reference, complete template, spec at ``ready`` or later.
- ``gh issue|pr edit|create|comment`` with body or label flags, ``gh pr review`` and ``gh issue|pr close``
  with a body, and direct REST/GraphQL writes to issues and pull requests through Bash are denied with
  the equivalent allowed route. Other commands are never touched.
- Body and comment writes carry the marker ``<!-- oct-src:1 -->``; status-system markers quoted in a
  comment are neutralised so they cannot be mistaken for real ones.
- Denials quote the next steps of the guide comment's data block when it can be read.

A hook that crashes is only a non-blocking error for Claude Code (the tool call proceeds), so ``main``
catches everything and exits with code 2 for write-class calls (fail closed).

Only the standard library and stdlib-only modules of this package may be imported here: the hook runs
on contributor machines without the automation's dependencies. Several patterns are copies of the
automation's; ``tests/test_hooks.py`` keeps them equal.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

if __package__ in (None, ""):  # run as a script: make `oct_status` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from oct_status.hooks import rest
    from oct_status.model import Phase

    IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - only on a broken checkout or Python < 3.11
    IMPORT_ERROR = exc

SRC_MARKER = "<!-- oct-src:1 -->"
GUIDE_MARKER = "<!-- oct-next:v1 -->"
WORKFLOW_ANCHOR = "docs/WORKFLOW.md#agents-and-subagents"
PROJECT_REPO = "opencloudtouch"  # the guard applies to this repository and its forks
BUDGET_SECONDS = 40.0  # overall REST budget of one run; the hook's timeout in settings.json is 60 s
MAX_COMMAND = 32_000  # longer GitHub-related Bash commands are denied instead of parsed
MAX_BODY = 65_000  # characters; GitHub rejects longer bodies (65,536)
MAX_SPEC_REFS = 5
STATUS_PREFIXES = ("phase:", "wait:", "resolution:")
# Labels the automation derives from facts; mirrors violations.FACT_LABELS.
FACT_LABELS = frozenset(
    {f"phase:{p}" for p in ("new", "draft", "in-progress", "in-review", "merged", "done", "closed", "verification")}
    | {f"wait:{w}" for w in ("maintainer", "findings", "ci", "prerequisite", "hardware-test")}
)
READY_OR_LATER = frozenset({"ready", "in-progress", "in-review", "verification", "done"})  # rules._READY_OR_LATER
CHORE_TYPES = frozenset({"docs", "ci", "chore", "style", "test"})  # rules._CHORE_TYPES

_BLOCK = re.compile(r"<!-- oct-status:v1 hash=[0-9a-f]{12} -->.*?<!-- /oct-status -->", re.DOTALL)  # render
_ANY_BLOCK_MARKER = re.compile(r"<!--\s*/?oct-status", re.IGNORECASE)
_STATUS_MARKER = re.compile(r"<!--(?=\s*/?oct-(?:status|next))", re.IGNORECASE)
_DATA = re.compile(r"<!-- oct-next-data (.*?) -->", re.DOTALL)
_SRC = re.compile(r"\s*<!-- oct-src:1 -->\s*")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")  # rules._HEADING, render._HEADING
_ITEM = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s*(.*?)\s*$")  # rules._ITEM, render._ITEM
_NOT_APPLICABLE = re.compile(r"\bn/a\b", re.IGNORECASE)  # rules._NOT_APPLICABLE
_CONVENTIONAL = re.compile(r"^(\w+)(?:\([^)]*\))?!?:")  # rules._CONVENTIONAL
_SPEC_REF = re.compile(r"\b(?:closes|part of)\s+#(\d+)", re.IGNORECASE)
_NO_SPEC = re.compile(r"^ {0,3}/oct[ \t]+no-spec[ \t]+\S", re.IGNORECASE | re.MULTILINE)
_BOT = re.compile(r"@?gitar-bot(\[bot\])?", re.IGNORECASE)
_LEADING = re.compile(r"^\s*@?gitar", re.IGNORECASE)
_UNSAFE = re.compile(r"[<>\x00-\x08\x0b-\x1f\x7f]")
# Maintainer commands (commands.MAINTAINER_COMMANDS) and the command parser's patterns (commands._COMMAND,
# _FENCE, _HTML_COMMENT): an agent session may not post them, the automation rejects them as well (I6).
MAINTAINER_COMMANDS = frozenset(
    {"triage", "confirm", "verified", "needs-hardware-test", "needs-info", "designer", "supersede", "override"}
    | {"accept-paths"}
)
_COMMAND = re.compile(r"^ {0,3}/oct(?:[ \t]+([A-Za-z][A-Za-z-]*))?(?:[ \t]+(.*))?$", re.IGNORECASE)
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HTML_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
_NEUTRAL = "<!--​"  # a zero-width space keeps a quoted marker from matching the real one

# Tool names (the part after the MCP server prefix) and their aliases in older GitHub MCP servers.
_ALIASES = {"create_issue": "issue_write", "update_issue": "issue_write", "create_issue_comment": "add_issue_comment"}
BODY_TOOLS = frozenset({"issue_write", "update_pull_request", "create_pull_request"})
COMMENT_TOOLS = frozenset(
    {
        "add_issue_comment",
        "update_issue_comment",
        "pull_request_review_write",
        "add_comment_to_pending_review",
        "add_reply_to_pull_request_comment",
    }
)
GUARDED_TOOLS = BODY_TOOLS | COMMENT_TOOLS

# The `/oct` route for each status label (design sections 4.3 and 11).
LABEL_ROUTES = {
    "phase:spec-review": "`/oct review`",
    "phase:spec-rework": "`/oct rework REASON`",
    "phase:ready": "`/oct ready --reviewer LOGIN` (or `--reviewer independent-review`)",
    "phase:triaged": "`/oct triage`",
    "phase:confirmed": "`/oct confirm`",
    "wait:maintainer": "`/oct approve` (requests the review that clears it)",
    "wait:hardware-test": "`/oct needs-hardware-test` to set it, `/oct verified DEVICE` to clear it",
    "wait:reporter": "`/oct needs-info`",
    "wait:designer": "`/oct designer REASON`",
    "wait:spec-fix": "`/oct rework REASON`",
    "resolution:superseded": "`/oct supersede #N`",
    # Discussion phases (discussions are not handled by the automation yet; no `/oct` command exists).
    "phase:open": "none: discussion phases are left to the maintainers",
    "phase:needs-spec": "none: discussion phases are left to the maintainers",
    "phase:specified": "none: discussion phases are left to the maintainers",
    "phase:answered": "none: discussion phases are left to the maintainers",
}
_FACT_ROUTE = "none: the automation derives it from GitHub state (pull requests, reviews, checks, open or closed)"
_RESOLUTION_ROUTE = "ask a maintainer to close the artifact with that resolution"

# --- Data types -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class SpecInfo:
    """A spec referenced by a new pull request, as far as it could be read."""

    number: int
    readable: bool = True
    is_spec: bool = True  # carries the label `spec`; other kinds are not gated
    phase: Phase | None = None  # from its `phase:*` label; None when it has none (not backfilled)
    waits: frozenset[str] = frozenset()  # its `wait:*` labels
    dor_complete: bool | None = None  # Definition of Ready checklist complete; None: legacy spec without one


@dataclass(frozen=True)
class HookContext:
    """What the guard knows about the artifact a tool call writes to.

    `block` is ``None`` when the current block could not be read and ``""`` when the artifact has none
    (new, not backfilled, or a Dependabot PR whose block lives in the guide comment). `has_template`
    says whether the pull request template could be read; its text is `template`. `labels` are the
    current labels (``None``: unknown). `specs` are the referenced specs of a new pull request and
    `stacked` whether its base branch is the head of another open pull request. `comment_body` is the
    current text of a comment being edited (``None``: unknown).
    """

    block: str | None = None
    guide_data: dict | None = None
    spec_phase: Phase | None = None  # phase of the first referenced spec (convenience, see `specs`)
    has_template: bool = False
    template: str = ""
    labels: frozenset[str] | None = None
    specs: tuple[SpecInfo, ...] = ()
    stacked: bool = False
    comment_body: str | None = None
    guide_number: int | None = None  # artifact whose guide data `guide_data` is


@dataclass(frozen=True)
class Decision:
    action: Literal["allow", "deny"]
    reason: str = ""
    updated_input: dict | None = None


@dataclass(frozen=True)
class Needs:
    """What `decide` needs to know about a tool call, so the wrapper reads only that."""

    owner: str = ""
    repo: str = ""
    artifact: int | None = None  # read its body (block) and labels
    comment_id: int | None = None  # read the comment being edited
    specs: tuple[int, ...] = ()  # read the referenced specs
    base: str | None = None  # check whether this branch is the head of an open pull request
    template: bool = False  # read the pull request template
    guide: int | None = None  # artifact whose guide data a denial would quote
    bash: bool = False


# --- Text helpers -----------------------------------------------------------------------------------


def safe(text: str) -> str:
    """Text the hook emits: no review-bot mention, never starting with the bot's trigger word."""
    text = _BOT.sub("the review bot", text)
    return "\n".join(f"Review by {line.lstrip()}" if _LEADING.match(line) else line for line in text.split("\n"))


def _plain(text: object, limit: int = 300) -> str:
    return " ".join(_UNSAFE.sub(" ", str(text)).split())[:limit]


def norm_label(label: object) -> str:
    """Label names compare case-insensitively and without surrounding blanks, as on GitHub."""
    return str(label).strip().casefold()


def extract_block(body: str) -> str | None:
    """Same as ``render.extract_block``."""
    match = _BLOCK.search((body or "").replace("\r\n", "\n"))
    return match.group(0) if match else None


def splice(body: str, block: str) -> str:
    """Put `block` at the top of `body`.

    Unlike ``render.splice_block`` (which replaces one block, ``count=1``, and shortens the relations
    table to a size limit), this drops every block an agent's text carries: an agent may have pasted
    several old ones. Oversized results are denied instead of shortened (`MAX_BODY`).
    """
    eol = "\r\n" if "\r\n" in body else "\n"
    rest_ = _BLOCK.sub("", body.replace("\r\n", "\n")).lstrip("\n")
    block = block.replace("\r\n", "\n")
    return (block + ("\n\n" + rest_ if rest_ else "")).replace("\n", eol)


def strip_blocks(body: str) -> str:
    eol = "\r\n" if "\r\n" in body else "\n"
    return _BLOCK.sub("", body.replace("\r\n", "\n")).lstrip("\n").replace("\n", eol)


def neutralise(text: str) -> str:
    """Quoted ``oct-status`` / ``oct-next`` markers in agent text can no longer match the real ones."""
    return _STATUS_MARKER.sub(_NEUTRAL, text)


def with_marker(body: str) -> str:
    """`body` ending with exactly one source marker; the status block and other markers stay untouched."""
    eol = "\r\n" if "\r\n" in body else "\n"
    text = _SRC.sub(eol, body).rstrip()
    return f"{text}{eol}{eol}{SRC_MARKER}" if text else SRC_MARKER


def parse_guide_data(body: str) -> dict | None:
    """The JSON of the guide comment's ``oct-next-data`` block, or ``None``."""
    match = _DATA.search(body or "")
    if match is None or len(match[1]) > 64_000:
        return None
    try:
        data = json.loads(match[1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def template_keys(body: str) -> set[str]:
    """Same keys as ``violations.template_keys``: headings and checklist items outside the block."""
    block = extract_block(body)
    text = _COMMENT.sub("", body.replace(block, "") if block else body or "")
    keys: set[str] = set()
    for line in text.splitlines():
        if m := _HEADING.match(line):
            keys.add("h:" + " ".join(m[2].casefold().split()))
        elif m := _ITEM.match(line):
            keys.add("i:" + " ".join(m[2].split(":")[0].casefold().split()))
    return keys


def dor_complete(body: str) -> bool | None:
    """Like ``rules.dor_status``: complete checklist? ``None`` when there is no DoR section (legacy spec)."""
    lines = (body or "").splitlines()
    level = start = 0
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and len(match[1]) in (2, 3) and match[2].lower() == "definition of ready":
            level, start = len(match[1]), index + 1
            break
    if not level:
        return None
    items = 0
    for line in lines[start:]:
        heading = _HEADING.match(line)
        if heading and len(heading[1]) <= level:
            break
        if item := _ITEM.match(line):
            items += 1
            if item[1] == " " and not _NOT_APPLICABLE.search(item[2]):
                return False
    return items > 0


def next_steps(data: dict | None, number: int | None = None) -> str:
    """The next steps of a guide data block as one quotable paragraph (empty when unavailable)."""
    if not isinstance(data, dict):
        return ""
    raw_steps, raw_waits = data.get("next"), data.get("waits")
    steps: list = raw_steps if isinstance(raw_steps, list) else []
    waits: list = raw_waits if isinstance(raw_waits, list) else []
    lines: list[str] = []
    for index, step in enumerate(steps[:5], 1):
        if not isinstance(step, dict):
            continue
        text = f"{index}. {_plain(step.get('actor', ''), 40)}: {_plain(step.get('text', ''))}"
        if isinstance(step.get("command"), str) and step["command"]:
            text += f" -> `{_plain(step['command'], 200)}`"
        lines.append(text)
    where = f" of #{number}" if number else ""
    head = f"Next steps from the guide comment{where} (phase {_plain(data.get('phase', '?'), 40)}"
    head += f", waiting on {', '.join(_plain(w, 40) for w in waits[:10]) or 'nothing'}):"
    return safe(" ".join([head, *lines]) if lines else f"{head} none listed.")


def maintainer_command(text: str) -> str | None:
    """The first maintainer command at the start of a line outside code fences and HTML comments (as the
    automation parses commands), or ``None``. Unlike the automation, every line is looked at, not only the
    first command."""
    fence: str | None = None
    for line in _HTML_COMMENT.sub("", text.replace("\r\n", "\n").replace("\r", "\n")).split("\n"):
        match = _FENCE.match(line)
        if fence is None:
            if match:
                fence = match[1]
                continue
            command = _COMMAND.match(line)
            if command and command[1] and command[1].lower() in MAINTAINER_COMMANDS:
                return command[1].lower()
        elif match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not line.strip(" `~"):
            fence = None
    return None


def _deny(problem: str, route: str, ctx: HookContext | None) -> Decision:
    parts = [f"oct-status guard: {problem}", f"Allowed route: {route}"]
    if ctx is not None and (steps := next_steps(ctx.guide_data, ctx.guide_number)):
        parts.append(steps)
    parts.append(f"Rules: {WORKFLOW_ANCHOR}.")
    return Decision("deny", safe(" ".join(parts)))


# --- MCP tools ----------------------------------------------------------------------------------------


def tool_key(tool_name: str) -> str:
    """``mcp__<server>__issue_write`` -> ``issue_write``; other names unchanged."""
    name = tool_name.rsplit("__", 1)[-1] if tool_name.startswith("mcp__") else tool_name
    return _ALIASES.get(name, name)


def _in_scope(tool_input: Mapping[str, Any]) -> bool:
    repo = tool_input.get("repo")
    return not isinstance(repo, str) or not repo or repo.strip().lower() == PROJECT_REPO


def _valid_names(tool_input: Mapping[str, Any]) -> bool:
    """Owner and repo, when given, are plain GitHub names (they end up in REST paths)."""
    return all(
        tool_input.get(key) in (None, "") or (isinstance(tool_input[key], str) and rest.NAME.match(tool_input[key]))
        for key in ("owner", "repo")
    )


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _method(name: str, tool_input: Mapping[str, Any], tool_name: str) -> str:
    if name == "issue_write":
        method = tool_input.get("method")
        if isinstance(method, str):
            return method
        return "create" if tool_name.endswith("create_issue") else "update"
    return ""


def spec_refs(body: str) -> list[int]:
    """Specs named with ``Closes #n`` / ``Part of #n`` outside HTML comments (the template's examples)."""
    return list(dict.fromkeys(int(n) for n in _SPEC_REF.findall(_COMMENT.sub("", body or ""))))


def needs_for(tool_name: str, tool_input: Mapping[str, Any]) -> Needs:
    """The reads `decide` depends on for this call."""
    if tool_name == "Bash":
        cmd = tool_input.get("command")
        ok = isinstance(cmd, str) and len(cmd) <= MAX_COMMAND
        return Needs(bash=True, guide=bash_artifact(cmd) if ok and isinstance(cmd, str) else None)
    name = tool_key(tool_name)
    if name not in GUARDED_TOOLS or not _in_scope(tool_input) or not _valid_names(tool_input):
        return Needs()
    owner, repo = str(tool_input.get("owner") or ""), str(tool_input.get("repo") or "")
    if name == "issue_write":
        number = _int(tool_input.get("issue_number"))
        update = _method(name, tool_input, tool_name) == "update"
        wants = update and ("body" in tool_input or "labels" in tool_input)
        return Needs(owner, repo, artifact=number if wants else None, guide=number if update else None)
    if name == "update_pull_request":
        number = _int(tool_input.get("pullNumber"))
        return Needs(owner, repo, artifact=number if "body" in tool_input else None, guide=number)
    if name == "create_pull_request":
        refs = spec_refs(str(tool_input.get("body") or ""))
        base = tool_input.get("base")
        return Needs(
            owner,
            repo,
            specs=tuple(refs) if len(refs) <= MAX_SPEC_REFS else (),
            base=base if isinstance(base, str) else None,
            template=True,
            guide=refs[0] if refs else None,
        )
    if name == "update_issue_comment":
        return Needs(owner, repo, comment_id=_int(tool_input.get("comment_id")))
    number = _int(tool_input.get("issue_number") or tool_input.get("pullNumber"))
    return Needs(owner, repo, guide=number)


def _label_route(label: str) -> str:
    if label in LABEL_ROUTES:
        return LABEL_ROUTES[label]
    if label in FACT_LABELS:
        return _FACT_ROUTE
    if label.startswith("resolution:"):
        return _RESOLUTION_ROUTE
    return "a `/oct` command; see the command reference in docs/WORKFLOW.md"


def _label_denial(changed: list[str], ctx: HookContext) -> Decision:
    routes = "; ".join(f"`{_plain(label, 60)}`: {_label_route(label)}" for label in sorted(changed))
    problem = (
        f"changing the status labels {', '.join(f'`{_plain(c, 60)}`' for c in sorted(changed))} by hand is not "
        "allowed (fact labels are derived, declarations are made with /oct commands; violation V02)."
    )
    return _deny(problem, f"post the command as a comment (add_issue_comment). {routes}.", ctx)


def _status_labels(labels: object) -> set[str]:
    if not isinstance(labels, list):
        return set()
    return {n for n in (norm_label(x) for x in labels) if n.startswith(STATUS_PREFIXES)}


def _check_labels(tool_input: Mapping[str, Any], update: bool, ctx: HookContext) -> Decision | None:
    if "labels" not in tool_input:
        return None
    wanted = _status_labels(tool_input.get("labels"))
    if not update:
        return _label_denial(sorted(wanted), ctx) if wanted else None
    if ctx.labels is None:
        return _deny(
            "the current labels could not be read, so a label change cannot be checked (fail closed).",
            "leave out `labels`, or retry when GitHub is reachable; status labels change only through /oct commands.",
            ctx,
        )
    current = _status_labels(list(ctx.labels))
    changed = sorted(wanted ^ current)
    return _label_denial(changed, ctx) if changed else None


def _too_long(body: str, ctx: HookContext) -> Decision | None:
    if len(body) <= MAX_BODY:
        return None
    return _deny(
        f"the text would have {len(body)} characters, more than GitHub accepts ({MAX_BODY}).",
        "shorten the text, or move details into a comment or a linked document.",
        ctx,
    )


def _description(body: str, ctx: HookContext, number: int | None, existing: bool) -> Decision | str:
    """A description with the current block spliced in (or without any block), or a denial."""
    if existing and ctx.block is None:
        what = f"#{number}" if number else "the artifact"
        return _deny(
            f"the current status block of {what} could not be read (offline, no token or rate limit), "
            "so the description cannot be written safely (fail closed).",
            "write your text as a comment instead (add_issue_comment); the description stays as it is.",
            ctx,
        )
    block = ctx.block if existing else ""
    text = neutralise_guide(body)
    if _ANY_BLOCK_MARKER.search(strip_blocks(text)):  # what is left besides valid (replaced) blocks
        return _deny(
            "the description carries an oct-status block marker that is not a valid block (violation V03).",
            "remove every `oct-status` marker from your text; the automation keeps the block at the top.",
            ctx,
        )
    final = with_marker(splice(text, block) if block else strip_blocks(text))
    return _too_long(final, ctx) or final


def neutralise_guide(text: str) -> str:
    """Neutralise only the guide comment markers (descriptions keep valid blocks for the splice)."""
    return re.sub(r"<!--(?=\s*oct-next)", _NEUTRAL, text, flags=re.IGNORECASE)


def _pr_gate(tool_input: Mapping[str, Any], ctx: HookContext) -> Decision | None:
    body = str(tool_input.get("body") or "")
    title = str(tool_input.get("title") or "").strip()
    match = _CONVENTIONAL.match(title)
    chore = bool(match and match.group(1).lower() in CHORE_TYPES)
    no_spec = bool(_NO_SPEC.search(_COMMENT.sub("", body)))
    refs = spec_refs(body)
    if not refs and not no_spec and not chore:
        return _deny(
            "the description names no spec (`Closes #n` or `Part of #n`) and has no `/oct no-spec REASON` "
            "(violation V01).",
            "add `Part of #SPEC` (or `Closes #SPEC` when this pull request completes the spec) under "
            "'Linked spec / issue'; for work without a spec use a docs/ci/chore/style/test title or put "
            "`/oct no-spec REASON` in the description and post the same command as a comment after creation.",
            ctx,
        )
    if len(refs) > MAX_SPEC_REFS:
        return _deny(
            f"the description references {len(refs)} issues with `Closes`/`Part of`; at most {MAX_SPEC_REFS} "
            "are checked.",
            "split the references: name the spec(s) this pull request implements and link the rest without "
            "`Closes`/`Part of`.",
            ctx,
        )
    if not ctx.has_template:
        return _deny(
            "the pull request template .github/pull_request_template.md could not be read (fail closed).",
            "run the session in a checkout of the repository and retry.",
            ctx,
        )
    missing = sorted(template_keys(ctx.template) - template_keys(body))
    if missing:
        shown = ", ".join(f"'{_plain(k[2:], 80)}'" for k in missing[:8])
        more = f" and {len(missing) - 8} more" if len(missing) > 8 else ""
        return _deny(
            f"the description lacks template sections or checklist items: {shown}{more} (violation V05).",
            "start from .github/pull_request_template.md, keep every heading and item, and mark items that do "
            "not apply as `n/a` with a reason.",
            ctx,
        )
    if not refs:  # exempt (no-spec or chore title) and nothing referenced
        return None
    known = {s.number: s for s in ctx.specs}
    for number in refs:  # a referenced spec is gated even with `/oct no-spec`
        spec = known.get(number)
        if spec is None or not spec.readable:
            return _deny(
                f"#{number} could not be read, so its readiness cannot be checked (fail closed).",
                "retry when GitHub is reachable.",
                ctx,
            )
        if not spec.is_spec:
            continue
        if spec.phase is None:
            if spec.dor_complete is False:
                return _deny(
                    f"spec #{number} has no phase label and its Definition of Ready is incomplete (violation V06).",
                    f"complete and review the spec first (`/oct review`, then `/oct ready` by the reviewer on #{number}).",
                    ctx,
                )
            continue  # not backfilled yet: a complete DoR (or a legacy spec) stands in for `ready`
        if spec.phase.value not in READY_OR_LATER:
            return _deny(
                f"spec #{number} is at phase `{spec.phase.value}`, below `ready` (violation V06).",
                f"implementation starts after the spec is ready; follow the next steps on #{number}.",
                ctx,
            )
        if "wait:prerequisite" in {norm_label(w) for w in spec.waits} and not ctx.stacked:
            return _deny(
                f"spec #{number} waits on a prerequisite that is not merged (violation V04).",
                "create the pull request with `base` set to the head branch of the prerequisite's pull request "
                "(stacked-on), or wait until the prerequisite is merged.",
                ctx,
            )
    return None


def _decide_tool(name: str, tool_name: str, tool_input: dict, ctx: HookContext) -> Decision:
    if not _valid_names(tool_input):
        return _deny("`owner` or `repo` is not a valid GitHub name (fail closed).", "pass plain names.", ctx)
    updated = dict(tool_input)
    raw = tool_input.get("body")
    has_body = isinstance(raw, str)  # an empty description is a write as well
    body = raw if isinstance(raw, str) else ""
    result: Decision | str
    if name == "issue_write":
        update = _method(name, tool_input, tool_name) == "update"
        if denial := _check_labels(tool_input, update, ctx):
            return denial
        if has_body:
            result = _description(body, ctx, _int(tool_input.get("issue_number")), existing=update)
            if isinstance(result, Decision):
                return result
            updated["body"] = result
    elif name == "update_pull_request":
        if has_body:
            result = _description(body, ctx, _int(tool_input.get("pullNumber")), existing=True)
            if isinstance(result, Decision):
                return result
            updated["body"] = result
    elif name == "create_pull_request":
        if denial := _pr_gate(tool_input, ctx):
            return denial
        result = _description(body, ctx, None, existing=False)
        if isinstance(result, Decision):
            return result
        updated["body"] = result
    else:
        if name == "update_issue_comment":
            if ctx.comment_body is None:
                return _deny(
                    "the comment being edited could not be read, so it cannot be told apart from the guide "
                    "comment (fail closed).",
                    "post a new comment instead (add_issue_comment).",
                    ctx,
                )
            if GUIDE_MARKER in ctx.comment_body:
                return _deny(
                    "this is the guide comment of the status automation; it is never edited or replied to.",
                    "post a new comment, with an `/oct` command if you want to change the state.",
                    ctx,
                )
        if body and (command := maintainer_command(body)):
            return _deny(
                f"`/oct {command}` is a maintainer command; the automation rejects it from an agent session "
                "(comments carry the source marker), so a maintainer must post it by hand.",
                f"ask the maintainer to post `/oct {command}` themselves; describe in your comment why it is needed.",
                ctx,
            )
        if body:
            final = with_marker(neutralise(body))
            if denial := _too_long(final, ctx):
                return denial
            updated["body"] = final
    if updated == tool_input:
        return Decision("allow")
    return Decision("allow", "oct-status guard: status block and source marker applied.", updated)


# --- Bash -----------------------------------------------------------------------------------------------

_SEPARATORS = set(";&|()<>\n")
_PREFIX_WORDS = {
    "command",
    "sudo",
    "env",
    "time",
    "exec",
    "nohup",
    "builtin",
    "noglob",
    "then",
    "do",
    "else",
    "elif",
    "if",
    "while",
    "until",
    "{",
    "}",
    "!",
    "$",
}
# Wrappers that run their arguments as a command, and their options that take a value.
_WRAPPERS = {
    "xargs": {"-I", "-i", "-L", "-l", "-n", "-P", "-d", "-E", "-e", "-s", "-a", "--delimiter", "--arg-file"},
    "npx": {"-p", "--package", "-c", "--call"},
}
_SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "pwsh", "powershell", "cmd"}
_QUIET = {"git", "echo", "printf", "grep", "egrep", "fgrep", "rg", "cat", "less", "head", "tail", "sed", "awk"}
_GH_BODY_FLAGS = {"-b", "--body", "-F", "--body-file", "-e", "--editor", "--edit-last", "-T", "--template"}
_GH_LABEL_FLAGS = {"--add-label", "--remove-label", "-l", "--label"}
_GH_FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}
_CURL_DATA = {
    "-d",
    "--data",
    "--data-raw",
    "--data-binary",
    "--data-urlencode",
    "--data-ascii",
    "--json",
    "-F",
    "--form",
    "--form-string",
    "-T",
    "--upload-file",
    "--post-data",
    "--post-file",
    "--body-data",
    "--body-file",
    "-Body",
    "-InFile",
}
_CURL_DATA_SHORT = set("dFT")  # short options in a cluster such as -sSd
_REPOS_ISSUES = re.compile(r"(?:^|/)repos/[^/\s]+/[^/\s]+/(?:issues|pulls)(?:[/?\s]|$)")
_API_ISSUES = re.compile(r"api\.github\.com/repos/[^/\s]+/[^/\s]+/(?:issues|pulls)(?:[/?\s'\"]|$)")
_MUTATION = re.compile(r"\bmutation\b")
_MUTATED = re.compile(r"(Issue|PullRequest|Comment|Label|Labelable|Review)\b")
_WRITE_METHOD = re.compile(r"\b(PATCH|POST|PUT|DELETE)\b")
_URL_NUMBER = re.compile(r"/(?:issues|pull|pulls)/(\d+)")
# A gh write at a command position (start, after a separator, a substitution or a keyword).
_LOOSE_GH = re.compile(
    r"(?:^|[;&|(\n`]|\$\(|\b(?:then|do|else|xargs|sudo|env|command|exec|eval)\s)\s*gh\s+(?:issue|pr)\s+"
    r"(?:edit|create|comment|review|close)\b"
)
_LOOSE_API = re.compile(r"api\.github\.com/(?:repos/\S+/(?:issues|pulls)|graphql)")
_HEREDOC = re.compile(r"<<(-?)[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_GH_WRITE_HINT = re.compile(r"\bgh\b|api\.github\.com")


def _drop_heredoc_bodies(command: str) -> str:
    """The command without here-document bodies (text, not commands; they may hold unbalanced quotes).

    Linear in the length of the command. A body is dropped only when its terminating delimiter line
    follows; otherwise the text stays and is judged as commands (nothing can be hidden behind an
    unterminated ``<<``).
    """
    lines = command.split("\n")
    last: dict[str, int] = {}  # last line index of each exact line
    last_tabs: dict[str, int] = {}  # the same with leading tabs removed (`<<-`)
    for index, line in enumerate(lines):
        last[line] = index
        last_tabs[line.lstrip("\t")] = index
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        out.append(line)
        index += 1
        pending = [
            (m[3], bool(m[1])) for m in _HEREDOC.finditer(line) if (last_tabs if m[1] else last).get(m[3], -1) >= index
        ]
        for delimiter, tabs in pending:  # bodies follow one after the other
            end = index
            while end < len(lines) and (lines[end].lstrip("\t") if tabs else lines[end]) != delimiter:
                end += 1
            if end >= len(lines):
                break  # not terminated after the previous body: keep the rest as commands
            out.append(lines[end])  # keep the delimiter line
            index = end + 1
    return "\n".join(out)


def _tokens(command: str) -> list[str]:
    lexer = shlex.shlex(_drop_heredoc_bodies(command), posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    return list(lexer)


def _substitutions(token: str) -> list[str]:
    """Commands inside ``$(...)`` and backticks of a word (for example a quoted argument)."""
    found: list[str] = []
    if "$(" in token:
        found.append(token[token.index("$(") + 2 :].rstrip().rstrip(")"))
    if token.count("`") >= 2:
        found.append(token.split("`")[1])
    return found


def _segments(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token and set(token) <= _SEPARATORS:
            segments.append([])
        elif token.startswith("`") and len(token) > 1:  # unquoted command substitution
            segments.append([token[1:]])
        else:
            segments[-1].append(token)
    return [s for s in segments if s]


def _strip_prefix(seg: list[str]) -> list[str]:
    index = 0
    while index < len(seg):
        token = seg[index]
        program = _program(token)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token, re.DOTALL) or token in _PREFIX_WORDS:
            index += 1
        elif program in _WRAPPERS:
            valued = _WRAPPERS[program]
            index += 1
            while index < len(seg) and seg[index].startswith("-"):
                flag = seg[index].split("=", 1)[0]
                index += 2 if flag in valued and "=" not in seg[index] and len(seg[index]) == len(flag) else 1
        else:
            break
    return seg[index:]


def _program(token: str) -> str:
    name = token.lstrip("`").replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _flag(token: str) -> str:
    return token.split("=", 1)[0] if token.startswith("--") else token


def _gh_repo_out_of_scope(args: list[str]) -> bool:
    for i, token in enumerate(args):
        value = None
        if token in ("-R", "--repo") and i + 1 < len(args):
            value = args[i + 1]
        elif token.startswith("--repo="):
            value = token.split("=", 1)[1]
        if value is not None:
            return value.rstrip("/").rsplit("/", 1)[-1].strip().lower() != PROJECT_REPO
    return False


def _label_values(args: list[str]) -> list[str]:
    values: list[str] = []
    for i, token in enumerate(args):
        flag = _flag(token)
        if flag not in _GH_LABEL_FLAGS:
            continue
        value = token.split("=", 1)[1] if "=" in token and token.startswith("--") else None
        if value is None and i + 1 < len(args):
            value = args[i + 1]
        values += [norm_label(v) for v in (value or "").split(",")]
    return values


def _gh_global(args: list[str]) -> list[str]:
    """Drop gh's global `-R/--repo` option in front of the command group."""
    while args and args[0] in ("-R", "--repo"):
        args = args[2:]
    while args and args[0].startswith("--repo="):
        args = args[1:]
    return args


def _gh(args: list[str], ctx: HookContext) -> Decision | None:
    if _gh_repo_out_of_scope(args):
        return None
    args = _gh_global(args)
    if len(args) < 2:
        return None
    group, verb = args[0], args[1]
    if group == "api":
        return _gh_api(args[1:], ctx)
    if group not in ("issue", "pr"):
        return None
    flags = {_flag(t) for t in args[2:]}
    if verb == "create" and group == "pr":
        return _deny(
            "`gh pr create` bypasses the pull request creation gate (spec reference, template, spec readiness).",
            "create the pull request with the GitHub MCP tool `create_pull_request`, which is checked by this guard.",
            ctx,
        )
    if verb == "review" and group == "pr" and flags & {"-b", "--body", "-F", "--body-file"}:
        return _deny(
            "`gh pr review` with a body writes past the guard.",
            "submit the review with the GitHub MCP tool `pull_request_review_write`, which adds the source marker.",
            ctx,
        )
    if verb == "close" and flags & {"-c", "--comment"}:
        return _deny(
            f"`gh {group} close` with a comment writes past the guard.",
            "post the comment with the GitHub MCP tool `add_issue_comment`, then close without `--comment`.",
            ctx,
        )
    if verb not in ("edit", "create", "comment"):
        return None
    statuses = [v for v in _label_values(args[2:]) if v.startswith(STATUS_PREFIXES) or "$" in v or "`" in v]
    if statuses:
        return _label_denial(statuses, ctx)
    if flags & _GH_BODY_FLAGS or "--fill" in flags or "--fill-first" in flags:
        if verb == "comment":
            route = "post the comment with the GitHub MCP tool `add_issue_comment`, which adds the source marker."
        elif verb == "create":
            route = "create the issue with the GitHub MCP tool `issue_write` (method `create`)."
        else:
            tool = "update_pull_request" if group == "pr" else "issue_write"
            route = (
                f"edit the description with the GitHub MCP tool `{tool}`, which splices the current status block in."
            )
        return _deny(f"`gh {group} {verb}` with a body writes past the status-block guard.", route, ctx)
    return None


def _api_route() -> str:
    return (
        "use the GitHub MCP tools (`issue_write`, `update_pull_request`, `create_pull_request`, "
        "`add_issue_comment`), which this guard checks; status labels change only through /oct commands."
    )


def _graphql_denial(ctx: HookContext, what: str) -> Decision:
    return _deny(f"{what} bypasses the guard.", _api_route(), ctx)


def _gh_api(args: list[str], ctx: HookContext) -> Decision | None:
    endpoint, method, has_fields, file_query = "", "GET", False, False
    i = 0
    while i < len(args):
        token, flag = args[i], _flag(args[i])
        if flag in ("-X", "--method"):
            value = token.split("=", 1)[1] if "=" in token and token.startswith("--") else None
            if value is None and i + 1 < len(args):
                value, i = args[i + 1], i + 1
            method = (value or "GET").upper()
        elif flag in _GH_FIELD_FLAGS:
            has_fields = True
            value = token.split("=", 1)[1] if "=" in token and token.startswith("--") else None
            if value is None and i + 1 < len(args):
                value, i = args[i + 1], i + 1
            if flag == "--input" or (value or "").split("=", 1)[-1].startswith("@"):
                file_query = True
        elif token.startswith("-X") and len(token) > 2:
            method = token[2:].upper()
        elif not token.startswith("-") and not endpoint:
            endpoint = token
        i += 1
    if endpoint.strip("/") == "graphql":
        if any(_MUTATION.search(a) and _MUTATED.search(a) for a in args):
            return _graphql_denial(ctx, "a GraphQL mutation of issues, pull requests, comments or labels")
        if file_query:
            return _graphql_denial(ctx, "a GraphQL query read from a file (it cannot be checked)")
        return None
    if method == "GET" and has_fields:
        method = "POST"
    if method != "GET" and _REPOS_ISSUES.search(endpoint.lstrip("/")):
        return _deny(f"`gh api` {method} on issues or pull requests bypasses the guard.", _api_route(), ctx)
    return None


def _http_client(program: str, args: list[str], ctx: HookContext) -> Decision | None:
    joined = " ".join(args)
    if "api.github.com" not in joined:
        return None
    method = "GET"
    for i, token in enumerate(args):
        flag = _flag(token)
        if flag in ("-X", "--request", "--method", "-Method") and i + 1 < len(args):
            method = args[i + 1].upper()
        elif token.startswith(("--request=", "--method=")):
            method = token.split("=", 1)[1].upper()
        elif re.fullmatch(r"-[A-Za-z]+", token) and "X" in token[1:]:
            rest_ = token[token.index("X", 1) + 1 :]
            method = (rest_ or (args[i + 1] if i + 1 < len(args) else "GET")).upper()
        elif flag in _CURL_DATA or (re.fullmatch(r"-[A-Za-z]{2,}", token) and set(token[1:]) & _CURL_DATA_SHORT):
            method = "POST" if method == "GET" else method
    if program in ("http", "https", "xh") and args and args[0].upper() in ("PATCH", "POST", "PUT", "DELETE"):
        method = args[0].upper()
    if "api.github.com/graphql" in joined and _MUTATION.search(joined) and _MUTATED.search(joined):
        return _graphql_denial(ctx, "a GraphQL mutation of issues, pull requests, comments or labels")
    if method != "GET" and _API_ISSUES.search(joined):
        return _deny(
            f"a direct {method} to the GitHub API on issues or pull requests bypasses the guard.", _api_route(), ctx
        )
    return None


def _segment(seg: list[str], ctx: HookContext, depth: int) -> Decision | None:
    seg = _strip_prefix(seg)
    if not seg:
        return None
    program, args = _program(seg[0]), seg[1:]
    if program == "gh":
        return _gh(args, ctx)
    if program in ("curl", "wget", "http", "https", "xh", "invoke-restmethod", "invoke-webrequest", "irm", "iwr"):
        return _http_client(program, args, ctx)
    if program == "eval" and depth < 3:
        return _decide_bash(" ".join(args), ctx, depth + 1)
    if program in _SHELLS and depth < 3:
        for i, token in enumerate(args[:-1]):
            if token.lower() in ("-c", "-lc", "/c", "-command"):
                return _decide_bash(args[i + 1], ctx, depth + 1)
        return None
    if program in _QUIET:  # text tools and git: their arguments are text, not requests
        return None
    raw = " ".join(seg)
    if "api.github.com" in raw and _WRITE_METHOD.search(raw) and _LOOSE_API.search(raw):
        return _deny(
            "a direct write to the GitHub API on issues or pull requests bypasses the guard.", _api_route(), ctx
        )
    return None


def _decide_bash(command: str, ctx: HookContext, depth: int = 0) -> Decision:
    try:
        segments = _segments(_tokens(command))
    except ValueError:  # unbalanced quotes: judge the raw text conservatively
        text = _drop_heredoc_bodies(command)
        loose_api = _LOOSE_API.search(text) and _WRITE_METHOD.search(text)
        if _LOOSE_GH.search(text) or (loose_api and not text.lstrip().startswith(tuple(f"{p} " for p in _QUIET))):
            return _deny(
                "the command could not be parsed and looks like a GitHub issue or pull request write.",
                _api_route(),
                ctx,
            )
        return Decision("allow")
    for seg in segments:
        if denial := _segment(seg, ctx, depth):
            return denial
        if depth < 3:
            for inner in (sub for token in seg for sub in _substitutions(token)):
                if (decision := _decide_bash(inner, ctx, depth + 1)).action == "deny":
                    return decision
    return Decision("allow")


def bash_artifact(command: str) -> int | None:
    """The issue or pull request number a guarded gh command targets (for quoting its guide data)."""
    try:
        segments = _segments(_tokens(command))
    except ValueError:
        return None
    for seg in segments:
        seg = _strip_prefix(seg)
        if seg and _program(seg[0]) == "gh":
            args = _gh_global(seg[1:])
            if len(args) >= 3 and args[0] in ("issue", "pr"):
                for token in args[2:]:
                    if token.isdigit():
                        return int(token)
                    if match := _URL_NUMBER.search(token):
                        return int(match[1])
    return None


# --- Entry ----------------------------------------------------------------------------------------------


def decide(tool_name: str, tool_input: dict, current: HookContext) -> Decision:
    """Allow (possibly with a rewritten input) or deny one tool call; pure."""
    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return Decision("allow")
        if len(command) > MAX_COMMAND:
            if not _GH_WRITE_HINT.search(command):
                return Decision("allow")
            return _deny(
                f"the command is longer than {MAX_COMMAND} characters and mentions GitHub, so it is not checked.",
                "split it into shorter commands, or write long texts to a file first.",
                current,
            )
        return _decide_bash(command, current)
    name = tool_key(tool_name)
    if name not in GUARDED_TOOLS or not _in_scope(tool_input):
        return Decision("allow")
    return _decide_tool(name, tool_name, tool_input, current)


def write_class(tool_name: str, tool_input: Mapping[str, Any]) -> bool:
    """Calls for which an internal error must block (fail closed)."""
    if tool_name == "Bash":
        command = tool_input.get("command")
        return isinstance(command, str) and bool(_GH_WRITE_HINT.search(command))
    return tool_key(tool_name) in GUARDED_TOOLS


def _phase(labels: set[str]) -> Phase | None:
    for label in sorted(labels):
        if label.startswith("phase:"):
            try:
                return Phase(label[len("phase:") :])
            except ValueError:
                continue
    return None


def _labels(issue: Mapping[str, Any]) -> set[str]:
    return {norm_label((x or {}).get("name")) for x in issue.get("labels") or [] if isinstance(x, dict)}


def _guide(api: rest.Rest, number: int) -> dict | None:
    try:
        comment = api.guide_comment(number)
    except rest.RestError:
        return None
    return parse_guide_data(comment.get("body") or "") if comment else None


def fetch_context(needs: Needs, api: rest.Rest | None, project: Path) -> HookContext:
    """Read what `needs` names; unreadable parts stay unknown (``None``) so `decide` fails closed."""
    block: str | None = None
    labels: frozenset[str] | None = None
    comment_body: str | None = None
    specs: list[SpecInfo] = []
    stacked = False
    template, has_template = "", False
    if needs.template:
        path = project / ".github" / "pull_request_template.md"
        try:
            template, has_template = path.read_text(encoding="utf-8"), True
        except OSError:
            pass
    if api is not None:
        if needs.artifact is not None:
            try:
                issue = api.issue(needs.artifact)
                block = extract_block(issue.get("body") or "") or ""
                labels = frozenset(_labels(issue))
            except rest.RestError:
                pass
        if needs.comment_id is not None:
            try:
                comment_body = str(api.comment(needs.comment_id).get("body") or "")
            except rest.RestError:
                pass
        for number in needs.specs:
            try:
                issue = api.issue(number)
            except rest.RestError:
                specs.append(SpecInfo(number, readable=False))
                continue
            names = _labels(issue)
            specs.append(
                SpecInfo(
                    number,
                    is_spec="spec" in names and "pull_request" not in issue,
                    phase=_phase(names),
                    waits=frozenset(n for n in names if n.startswith("wait:")),
                    dor_complete=dor_complete(issue.get("body") or ""),
                )
            )
        if needs.base:
            try:
                stacked = api.open_pull_for_head(needs.base) is not None
            except rest.RestError:
                stacked = False
    else:
        specs = [SpecInfo(number, readable=False) for number in needs.specs]
    return HookContext(
        block=block,
        spec_phase=specs[0].phase if specs else None,
        has_template=has_template,
        template=template,
        labels=labels,
        specs=tuple(specs),
        stacked=stacked,
        comment_body=comment_body,
        guide_number=needs.guide,
    )


def _wants_reads(needs: Needs) -> bool:
    return bool(needs.artifact is not None or needs.comment_id is not None or needs.specs or needs.base)


ApiFactory = Callable[[str, str], "rest.Rest | None"]


def output(decision: Decision, permission_mode: object) -> dict | None:
    """The hook's JSON answer, or ``None`` for "no opinion" (the normal permission flow continues).

    A rewritten input needs a decision. ``allow`` would also skip the permission prompt, so it is used
    only where the session skips prompts anyway (``bypassPermissions``); every other mode, including
    unknown ones, gets ``ask`` and the user sees the rewritten call.
    """
    if decision.action == "deny":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": decision.reason,
            }
        }
    if decision.updated_input is None:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow" if permission_mode == "bypassPermissions" else "ask",
            "permissionDecisionReason": decision.reason,
            "updatedInput": decision.updated_input,
        }
    }


def run(event: Mapping[str, Any], env: Mapping[str, str], api_for: ApiFactory) -> dict | None:
    tool_name = str(event.get("tool_name") or "")
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    needs = needs_for(tool_name, tool_input)
    project = rest.project_dir(env, event)
    api = api_for(needs.owner, needs.repo) if _wants_reads(needs) else None
    ctx = fetch_context(needs, api, project)
    decision = decide(tool_name, tool_input, ctx)
    if decision.action == "deny" and needs.guide is not None:
        if needs.bash:
            found = rest.origin_repo(project)
            api = api_for(*found) if found else None
        elif api is None:
            api = api_for(needs.owner, needs.repo)
        guide = _guide(api, needs.guide) if api is not None else None
        if guide is not None:
            decision = decide(tool_name, tool_input, replace(ctx, guide_data=guide))
    return output(decision, event.get("permission_mode"))


def main(
    stdin: Any = None,
    stdout: Any = None,
    stderr: Any = None,
    env: Mapping[str, str] | None = None,
    api_for: ApiFactory | None = None,
) -> int:
    deadline = time.monotonic() + BUDGET_SECONDS
    stdin, stdout, stderr = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    env = os.environ if env is None else env
    event: Any = {}
    try:
        for stream in (stdin, stdout, stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
        event = json.loads(stdin.read() or "{}")
        if IMPORT_ERROR is not None:  # pragma: no cover
            raise IMPORT_ERROR
        answer = run(event, env, api_for or rest.factory(env, deadline))
        if answer is not None:
            stdout.write(json.dumps(answer, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - a crashing hook would let the call through
        tool_name = str(event.get("tool_name") or "") if isinstance(event, dict) else ""
        tool_input = event.get("tool_input") if isinstance(event, dict) else None
        if not tool_name or write_class(tool_name, tool_input if isinstance(tool_input, dict) else {}):
            stderr.write(
                f"oct-status guard failed ({type(exc).__name__}) and blocks this GitHub write (fail closed). "
                f"Check that `python` is Python 3.11+ and the checkout is complete; see {WORKFLOW_ANCHOR}.\n"
            )
            return 2
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
