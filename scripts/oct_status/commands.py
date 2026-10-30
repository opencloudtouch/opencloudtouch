"""`/oct` commands: parse, authorize, execute (design section 11).

Comment text is untrusted. A command is only recognised at the start of a line, outside code fences,
HTML comments and quotes; arguments are stripped of control characters and length-limited, validated
with strict patterns, and never interpolated into a shell. Authorization fails closed: any API error
or unknown permission means "not authorized".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from .api import GitHubApi
from .apply import _comments
from .config import Config
from .facts import author_permission
from .model import Derived, Kind, Phase, Snapshot, Wait
from .rules import OCT_SUPPORT, detect_kind, dor_status, legal_transitions

MAX_ARGS = 300
INDEPENDENT_REVIEW = "independent-review"
WRITE_PERMISSIONS = frozenset({"admin", "maintain", "write"})
MAINTAINER_COMMANDS = frozenset(
    {"triage", "confirm", "verified", "needs-hardware-test", "needs-info", "designer", "supersede", "override"}
    | {"accept-paths"}
)
COMMANDS = frozenset(MAINTAINER_COMMANDS | {"review", "rework", "ready", "approve", "no-spec"})
# Commands whose argument is a mandatory free-text reason or note.
_NEEDS_TEXT = frozenset({"rework", "verified", "designer", "no-spec", "override"})

# Commands that declare a state; a rejected one is an invalid declaration (violation V07).
DECLARATION_COMMANDS = frozenset({"review", "rework", "ready", "triage", "confirm"})
_NOT_EFFECTIVE = {"accept-paths": "recorded in the guide only; it has no effect yet"}
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_COMMAND = re.compile(r"^ {0,3}/oct(?:[ \t]+([A-Za-z][A-Za-z-]*))?(?:[ \t]+(.*))?$", re.IGNORECASE)
_HTML_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_REVIEWER = re.compile(r"--reviewer(?:[ \t]+|=)(\S+)", re.IGNORECASE)
_ISSUE_REF = re.compile(r"#(\d+)")


@dataclass(frozen=True)
class Command:
    name: str
    args: str


@dataclass
class Outcome:
    ok: bool
    message: str
    declare: dict[str, list[str]] = field(default_factory=dict)  # {"add": [...labels], "remove": [...labels]}
    effects: list[str] = field(default_factory=list)  # other writes performed (planned in dry-run)
    log: str | None = None  # entry for the ledger (override, accept-paths)
    no_spec_reason: str | None = None


def _strip_noise(text: str) -> list[str]:
    """Lines of `text` outside code fences and HTML comments."""
    lines: list[str] = []
    fence: str | None = None
    for line in _HTML_COMMENT.sub("", text.replace("\r\n", "\n").replace("\r", "\n")).split("\n"):
        match = _FENCE.match(line)
        if fence is None:
            if match:
                fence = match[1]
                continue
            lines.append(line)
        elif match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not line.strip(" `~"):
            fence = None
    return lines


def parse_command(text: str) -> Command | None:
    """The first `/oct <command> [args]` at the start of a line, or ``None``.

    Unknown command names do not parse (the text is most likely prose). ``/octopus`` never parses.
    """
    for line in _strip_noise(text or ""):
        match = _COMMAND.match(line)
        if not match or not match[1]:
            continue
        name = match[1].lower()
        if name not in COMMANDS:
            continue
        args = _CONTROL.sub(" ", match[2] or "").strip()[:MAX_ARGS].strip()
        return Command(name, args)
    return None


def valid_login(login: str) -> bool:
    return bool(_LOGIN.fullmatch(login or ""))


async def _permission(api: GitHubApi, login: str) -> tuple[str | None, bool]:
    """Role of `login` and whether it could be verified (False after an API or parsing error)."""
    if not valid_login(login):  # the login ends up in a URL path
        return None, True
    try:
        return await author_permission(api, login), True
    except (httpx.HTTPError, ValueError, AttributeError):
        return None, False


async def authorize_detailed(api: GitHubApi, login: str, cmd: Command, cfg: Config) -> tuple[bool, str]:
    """Whether `login` may run `cmd`, and the reason when not."""
    needed = "maintain" if cmd.name in MAINTAINER_COMMANDS else "write"
    if login in cfg.automation or login in cfg.bot_logins:
        return False, f"/oct {cmd.name} cannot be run by automation accounts"
    permission, verified = await _permission(api, login)
    if not verified:
        return False, f"your permission could not be verified, try again later (/oct {cmd.name} needs {needed} access)"
    allowed = cfg.maintainer_permissions if needed == "maintain" else WRITE_PERMISSIONS
    if permission in allowed:
        return True, ""
    return False, f"/oct {cmd.name} needs {needed} access"


async def authorize(api: GitHubApi, login: str, cmd: Command, cfg: Config) -> bool:
    """Write access is required for every command, maintain or admin for the maintainer commands."""
    return (await authorize_detailed(api, login, cmd, cfg))[0]


def _reject(message: str) -> Outcome:
    return Outcome(False, message)


def _declare(snap: Snapshot, add: list[str], remove: list[str] | None = None, keep_phase: bool = False) -> dict:
    """Label changes; a phase declaration replaces every other phase label (derive takes the furthest)."""
    drop = list(remove or [])
    if not keep_phase:
        drop += [lb for lb in snap.labels if lb.startswith("phase:") and lb not in add]
    return {
        "add": [lb for lb in add if lb not in snap.labels],
        "remove": sorted({lb for lb in drop if lb in snap.labels}),
    }


def _transition(cmd: Command, snap: Snapshot, derived: Derived, cfg: Config, *, needs_dor: bool) -> Outcome | None:
    """Rejection when `cmd` is not a legal transition now, else ``None``."""
    kind = detect_kind(snap, cfg)
    if cmd.name not in legal_transitions(kind, derived.phase):
        legal = legal_transitions(kind, derived.phase)
        now = ", ".join(f"/oct {c}" for c in legal) or "none"
        return _reject(f"/oct {cmd.name} is not valid for a {kind.value} in phase {derived.phase.value}; valid: {now}")
    if needs_dor:
        complete, open_items = dor_status(snap.body)
        if not complete:
            return _reject(f"The Definition of Ready is incomplete. Open: {'; '.join(open_items)}")
    return None


async def _approve(api: GitHubApi, snap: Snapshot, actor: str, cfg: Config, dry_run: bool) -> Outcome:
    if not snap.is_pr or snap.state != "open" or snap.merged:
        return _reject("/oct approve only applies to an open pull request")
    if actor != snap.author and (await _permission(api, actor))[0] not in cfg.maintainer_permissions:
        return _reject("/oct approve may only be used by the PR author or a maintainer")
    if dry_run:
        return Outcome(True, f"would request the review by {OCT_SUPPORT}", effects=[f"request review {OCT_SUPPORT}"])
    resp = await api.request("POST", f"/pulls/{snap.number}/requested_reviewers", json={"reviewers": [OCT_SUPPORT]})
    if resp.status_code >= 300:
        return _reject(f"GitHub refused the review request (HTTP {resp.status_code})")
    return Outcome(True, f"requested the review by {OCT_SUPPORT}", effects=[f"request review {OCT_SUPPORT}"])


def _ready(cmd: Command, snap: Snapshot, actor: str) -> Outcome | None:
    match = _REVIEWER.fullmatch(cmd.args)
    reviewer = match[1] if match else ""
    if not reviewer or not (reviewer == INDEPENDENT_REVIEW or valid_login(reviewer)):
        return _reject('/oct ready needs --reviewer <login or "independent-review">')
    if reviewer != INDEPENDENT_REVIEW and reviewer.lower() == snap.author.lower():
        return _reject(f'The reviewer must differ from the author {snap.author}, or be "{INDEPENDENT_REVIEW}"')
    if actor.lower() == snap.author.lower() and reviewer != INDEPENDENT_REVIEW:
        return _reject(f"The author cannot declare the spec ready; use --reviewer {INDEPENDENT_REVIEW}")
    return None


async def execute(
    api: GitHubApi,
    cmd: Command,
    snap: Snapshot,
    derived: Derived | None,
    actor: str,
    *,
    cfg: Config,
    dry_run: bool = False,
) -> Outcome:
    """Run an authorized command. Label changes are returned in `declare`; the caller applies them.

    The only write done here is the review request of ``approve`` (never in `dry_run`).
    """
    name = cmd.name
    if derived is None:
        return _reject("Announcements have no workflow state")
    if name in _NEEDS_TEXT and not cmd.args:
        return _reject(f"/oct {name} needs a reason or note")
    if name == "approve":
        return await _approve(api, snap, actor, cfg, dry_run)
    if name == "no-spec":
        if not snap.is_pr:
            return _reject("/oct no-spec only applies to a pull request")
        if actor != snap.author:
            return _reject("/oct no-spec may only be used by the PR author")
        return Outcome(True, f"no spec needed: {cmd.args}", no_spec_reason=cmd.args)
    if name == "review" or name == "rework" or name == "ready":
        if detect_kind(snap, cfg) != Kind.SPEC:
            return _reject(f"/oct {name} only applies to a spec")
        if name == "review" and actor != snap.author:
            return _reject("/oct review may only be used by the spec author")
        if name == "ready" and (rejected := _ready(cmd, snap, actor)) is not None:
            return rejected
        if rejected := _transition(cmd, snap, derived, cfg, needs_dor=name != "rework"):
            return rejected
        if name == "rework":
            declare = _declare(snap, [Phase.SPEC_REWORK.label, Wait.SPEC_FIX.label])
            return Outcome(True, f"spec sent back for rework: {cmd.args}", declare)
        phase = Phase.SPEC_REVIEW if name == "review" else Phase.READY
        declare = _declare(snap, [phase.label], [Wait.SPEC_FIX.label])
        return Outcome(True, f"spec is now {phase.value}" + (f" ({cmd.args})" if name == "ready" else ""), declare)
    if name in ("triage", "confirm"):
        phase = Phase.TRIAGED if name == "triage" else Phase.CONFIRMED
        if rejected := _transition(cmd, snap, derived, cfg, needs_dor=False):
            return rejected
        return Outcome(True, f"marked {phase.value}", _declare(snap, [phase.label]))
    if name == "verified":
        return Outcome(True, f"verified: {cmd.args}", _declare(snap, [], [Wait.HARDWARE_TEST.label], keep_phase=True))
    waits = {"needs-hardware-test": Wait.HARDWARE_TEST, "needs-info": Wait.REPORTER, "designer": Wait.DESIGNER}
    if name in waits:
        wait = waits[name]
        suffix = f": {cmd.args}" if cmd.args else ""
        return Outcome(True, f"now waiting on {wait.value}{suffix}", _declare(snap, [wait.label], keep_phase=True))
    if name == "supersede":
        ref = _ISSUE_REF.fullmatch(cmd.args)
        if not ref or int(ref[1]) == snap.number:
            return _reject("/oct supersede needs the number of another artifact, for example #123")
        if snap.state == "open":
            return _reject("Close the artifact first: a resolution applies to closed artifacts only")
        return Outcome(True, f"superseded by #{ref[1]}", _declare(snap, ["resolution:superseded"], keep_phase=True))
    # override is written to the ledger by the caller; accept-paths is logged only until protected paths (Task 14)
    detail = f": {cmd.args}" if cmd.args else ""
    message = f"override accepted: {cmd.args}" if name == "override" else _NOT_EFFECTIVE[name]
    return Outcome(True, message, log=f"{name} by {actor}{detail}")


async def apply_declaration(api: GitHubApi, number: int, declare: dict[str, list[str]], *, dry_run: bool) -> list[str]:
    """Write the label changes of a declaration; returns what was (planned if `dry_run`) done."""
    done: list[str] = []
    add, remove = declare.get("add", []), declare.get("remove", [])
    if add:
        if not dry_run:
            (await api.request("POST", f"/issues/{number}/labels", json={"labels": add})).raise_for_status()
        done.append(f"add labels {', '.join(add)}")
    for label in remove:
        if not dry_run:
            resp = await api.request("DELETE", f"/issues/{number}/labels/{quote(label, safe='')}")
            if resp.status_code != 404:
                resp.raise_for_status()
        done.append(f"remove label {label}")
    return done


async def react(api: GitHubApi, comment_id: int, content: str, *, dry_run: bool) -> bool:
    """Best-effort reaction (``eyes``, ``+1``, ``-1``) on the command comment; never in `dry_run`."""
    if dry_run:
        return False
    try:
        resp = await api.request("POST", f"/issues/comments/{comment_id}/reactions", json={"content": content})
    except httpx.HTTPError:
        return False
    return resp.status_code < 300


async def find_no_spec(api: GitHubApi, snap: Snapshot) -> str | None:
    """Reason of the latest `/oct no-spec` written by the PR author (who needs write access)."""
    if not snap.is_pr or snap.author_permission not in WRITE_PERMISSIONS:
        return None
    reason: str | None = None
    for comment in await _comments(api, snap.number):
        if (comment.get("user") or {}).get("login") != snap.author:
            continue
        cmd = parse_command(comment.get("body") or "")
        if cmd is not None and cmd.name == "no-spec" and cmd.args:
            reason = cmd.args
    return reason
