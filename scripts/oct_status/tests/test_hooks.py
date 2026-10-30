"""Agent hooks: PreToolUse guard and SessionStart context (design section 8)."""

from __future__ import annotations

import io
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from oct_status import render, rules, violations
from oct_status.config import load_config
from oct_status.hooks import guard, rest, session_start
from oct_status.hooks.guard import Decision, HookContext, SpecInfo, decide
from oct_status.model import Phase

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
BLOCK = "<!-- oct-status:v1 hash=0123456789ab -->\n**phase:ready**\n| a | b |\n<!-- /oct-status -->"
STALE = "<!-- oct-status:v1 hash=ffffffffffff -->\nold\n<!-- /oct-status -->"
GUIDE_DATA = {
    "phase": "in-review",
    "waits": ["maintainer"],
    "next": [
        {"actor": "author", "text": "Request the AI review", "command": "/oct approve"},
        {"actor": "maintainer", "text": "Ask @gitar-bot to look again", "command": None},
    ],
}
MCP = "mcp__github__"


def _guide_body(data: dict | None = None) -> str:
    return f"<!-- oct-next:v1 -->\n### Last action\n-\n<!-- oct-next-data {json.dumps(data or GUIDE_DATA)} -->\n"


def _issue_write(**extra) -> dict:
    return {"method": "update", "owner": "opencloudtouch", "repo": "opencloudtouch", "issue_number": 42, **extra}


def _pr_body(spec: str = "Part of #537") -> str:
    return TEMPLATE.replace('<!-- "Closes #123"', f'{spec}\n<!-- "Closes #123"')


def _create(body: str, title: str = "feat(oct-status): add hooks", base: str = "main") -> dict:
    return {
        "owner": "opencloudtouch",
        "repo": "opencloudtouch",
        "title": title,
        "head": "feat/x",
        "base": base,
        "body": body,
    }


READY_SPEC = SpecInfo(537, phase=Phase.READY)
PR_CTX = HookContext(has_template=True, template=TEMPLATE, specs=(READY_SPEC,), spec_phase=Phase.READY)


# --- The eight scenarios of the plan -------------------------------------------------------------------


def test_body_write_gets_block_spliced():
    ctx = HookContext(block=BLOCK, labels=frozenset())
    d = decide(MCP + "issue_write", _issue_write(body=f"{STALE}\n\nNew text"), ctx)
    assert d.action == "allow"
    assert d.updated_input is not None
    body = d.updated_input["body"]
    assert body.startswith(BLOCK + "\n\nNew text")
    assert "old" not in body
    assert render.extract_block(body) == BLOCK
    # The same goes for pull request descriptions; untouched fields are kept.
    pr = {"owner": "opencloudtouch", "repo": "opencloudtouch", "pullNumber": 7, "body": "Text", "title": "t"}
    d = decide(MCP + "update_pull_request", pr, ctx)
    assert d.updated_input is not None and d.updated_input["title"] == "t"
    assert d.updated_input["body"].startswith(BLOCK)


def test_body_write_denied_when_block_unreadable():
    ctx = HookContext(block=None, labels=None)
    d = decide(MCP + "issue_write", _issue_write(body="New text"), ctx)
    assert d.action == "deny"
    assert "fail closed" in d.reason and "comment instead" in d.reason and "add_issue_comment" in d.reason
    pr = {"owner": "opencloudtouch", "repo": "opencloudtouch", "pullNumber": 7, "body": "Text"}
    assert decide(MCP + "update_pull_request", pr, ctx).action == "deny"


def test_fact_label_write_denied_with_oct_alternative():
    ctx = HookContext(block=BLOCK, labels=frozenset({"spec", "phase:draft"}))
    d = decide(MCP + "issue_write", _issue_write(labels=["spec", "phase:in-progress"]), ctx)
    assert d.action == "deny"
    assert "phase:in-progress" in d.reason and "phase:draft" in d.reason
    assert "derives it from GitHub state" in d.reason
    d = decide(MCP + "issue_write", _issue_write(labels=["spec", "phase:ready"]), ctx)
    assert "/oct ready --reviewer LOGIN" in d.reason
    # Foreign labels pass; status labels kept as they are pass too.
    assert decide(MCP + "issue_write", _issue_write(labels=["spec", "phase:draft", "ux"]), ctx).action == "allow"
    # Unknown current labels: fail closed.
    assert decide(MCP + "issue_write", _issue_write(labels=["spec"]), replace(ctx, labels=None)).action == "deny"
    # A new issue cannot carry a status label.
    create = {"method": "create", "owner": "o", "repo": "opencloudtouch", "title": "t", "labels": ["wait:reporter"]}
    d = decide(MCP + "issue_write", create, HookContext())
    assert d.action == "deny" and "/oct needs-info" in d.reason
    d = decide(MCP + "issue_write", {**create, "labels": ["resolution:wontfix"]}, HookContext())
    assert "maintainer" in d.reason


def test_pr_creation_gate():
    gate = MCP + "create_pull_request"
    # No spec reference and no /oct no-spec.
    d = decide(gate, _create(TEMPLATE), PR_CTX)
    assert d.action == "deny" and "V01" in d.reason
    # The template's own example inside an HTML comment does not count.
    assert "Closes #123" in TEMPLATE
    # Template heading missing, item deleted.
    no_heading = _pr_body().replace("## Open verifications and follow-ups", "")
    d = decide(gate, _create(no_heading), PR_CTX)
    assert d.action == "deny" and "open verifications and follow-ups" in d.reason
    no_item = _pr_body().replace("- [ ] PR title and commits follow Conventional Commits\n", "")
    d = decide(gate, _create(no_item), PR_CTX)
    assert d.action == "deny" and "pr title and commits follow conventional commits" in d.reason
    # Template unreadable: fail closed.
    assert decide(gate, _create(_pr_body()), replace(PR_CTX, has_template=False)).action == "deny"
    # Spec below ready.
    draft = replace(PR_CTX, specs=(SpecInfo(537, phase=Phase.SPEC_REVIEW),))
    d = decide(gate, _create(_pr_body()), draft)
    assert d.action == "deny" and "below `ready`" in d.reason
    # Spec ready but waiting on a prerequisite: denied unless stacked on it.
    waiting = replace(PR_CTX, specs=(SpecInfo(537, phase=Phase.READY, waits=frozenset({"wait:prerequisite"})),))
    d = decide(gate, _create(_pr_body()), waiting)
    assert d.action == "deny" and "stacked-on" in d.reason
    d = decide(gate, _create(_pr_body(), base="feat/560-prerequisite"), replace(waiting, stacked=True))
    assert d.action == "allow"
    assert d.updated_input is not None and d.updated_input["body"].endswith(guard.SRC_MARKER)
    # Ready spec: allowed.
    assert decide(gate, _create(_pr_body()), PR_CTX).action == "allow"
    # Spec not readable: fail closed; referenced issue that is no spec: not gated.
    assert decide(gate, _create(_pr_body()), replace(PR_CTX, specs=(SpecInfo(537, readable=False),))).action == "deny"
    assert decide(gate, _create(_pr_body()), replace(PR_CTX, specs=())).action == "deny"
    bug = replace(PR_CTX, specs=(SpecInfo(537, is_spec=False),))
    assert decide(gate, _create(_pr_body()), bug).action == "allow"
    # Not backfilled yet: the DoR checklist decides; a legacy spec without one passes.
    assert (
        decide(gate, _create(_pr_body()), replace(PR_CTX, specs=(SpecInfo(537, dor_complete=False),))).action == "deny"
    )
    assert (
        decide(gate, _create(_pr_body()), replace(PR_CTX, specs=(SpecInfo(537, dor_complete=None),))).action == "allow"
    )
    # Exempt: /oct no-spec in the body, or a chore-type title (template still required).
    no_spec = TEMPLATE + "\n/oct no-spec tooling only\n"
    assert decide(gate, _create(no_spec), replace(PR_CTX, specs=())).action == "allow"
    assert decide(gate, _create(TEMPLATE, title="docs: fix typo"), replace(PR_CTX, specs=())).action == "allow"
    assert decide(gate, _create("short", title="docs: fix typo"), PR_CTX).action == "deny"


@pytest.mark.parametrize(
    ("command", "route"),
    [
        ('gh issue edit 42 --body "new"', "issue_write"),
        ("gh pr edit 7 -b new", "update_pull_request"),
        ("gh pr edit 7 --body-file body.md", "update_pull_request"),
        ('gh issue comment 42 --body "hi"', "add_issue_comment"),
        ('gh issue create --title t --body "b"', "issue_write"),
        ("gh pr create --fill", "create_pull_request"),
        ("gh pr create --title t --body \"$(cat <<'EOF'\nbody\nEOF\n)\"", "create_pull_request"),
        ("cat <<EOF\nx\nEOF\ngh issue comment 4 -b y", "add_issue_comment"),
        ("echo `gh pr edit 7 -b x`", "update_pull_request"),
        ("cat <<EOF\nit's\nEOF\ngh issue edit 4 --body y", "issue_write"),
        ("cat <<EOF\nno end it's\ngh issue edit 4 --body y", "MCP tools"),  # body never ends: nothing dropped
        ("gh issue edit 42 --add-label phase:ready", "/oct ready"),
        ("gh pr edit 7 --remove-label=wait:maintainer", "/oct approve"),
        ('gh api -X PATCH repos/o/opencloudtouch/issues/42 -f body="x"', "MCP tools"),
        ("gh api repos/o/opencloudtouch/issues/42/labels -f labels[]=phase:ready", "MCP tools"),
        ("gh api --method=POST /repos/o/opencloudtouch/issues/42/comments -F body=@f", "MCP tools"),
        ("gh api graphql -f query='mutation { addComment(input: {}) { clientMutationId } }'", "MCP tools"),
        ("curl -X PATCH https://api.github.com/repos/o/opencloudtouch/issues/42 -d '{}'", "MCP tools"),
        ("curl -s https://api.github.com/repos/o/opencloudtouch/pulls/7 --data '{}'", "MCP tools"),
        ("wget --method=PATCH https://api.github.com/repos/o/opencloudtouch/issues/42", "MCP tools"),
        ("http PATCH https://api.github.com/repos/o/opencloudtouch/issues/42 body=x", "MCP tools"),
        ('curl -XPOST https://api.github.com/graphql -d \'{"query": "mutation { updateIssue }"}\'', "MCP tools"),
        ("python -c \"requests.patch('https://api.github.com/repos/o/r/issues/1')\" PATCH", "MCP tools"),
        ('cd x && FOO=1 gh issue edit 42 --body "n"', "issue_write"),
        ('echo "$(gh pr edit 7 -b x)"', "update_pull_request"),
        ("bash -c 'gh issue edit 42 --body x'", "issue_write"),
        ("eval gh issue edit 42 --body x", "issue_write"),
        ("gh issue edit 42 --body \"it's \n", "MCP tools"),  # unparsable, judged on the raw text
        ('gh issue edit 42 --add-label "$L"', "/oct"),
        ('gh issue close 5 -c "comment"', "add_issue_comment"),
        ("gh pr close 5 --comment x", "add_issue_comment"),
        ('gh pr review 5 --approve -b "x"', "pull_request_review_write"),
        ("curl -sSd x https://api.github.com/repos/o/opencloudtouch/issues/5", "MCP tools"),
        ("curl https://api.github.com/repos/o/opencloudtouch/issues/5/labels --data-ascii x", "MCP tools"),
        ("curl --upload-file f https://api.github.com/repos/o/opencloudtouch/issues/5", "MCP tools"),
        ("curl -sXPATCH https://api.github.com/repos/o/opencloudtouch/issues/5", "MCP tools"),
        ("curl -sX PATCH https://api.github.com/repos/o/opencloudtouch/issues/5", "MCP tools"),
        ("gh api graphql -F query=@mut.graphql", "MCP tools"),
        ("gh api graphql --input q.json", "MCP tools"),
        ("if true; then gh issue edit 5 --body x; fi", "issue_write"),
        ("{ gh issue edit 5 --body x; }", "issue_write"),
        ("for i in 1 2; do gh issue edit $i --body x; done", "issue_write"),
        ("while true; do gh pr edit 5 -b x; done", "update_pull_request"),
        ("until false; do gh pr edit 5 -b x; done", "update_pull_request"),
        ("if false; then :; else gh pr edit 5 -b x; fi", "update_pull_request"),
        ("! gh issue edit 5 --body x", "issue_write"),
        ("npx gh issue edit 5 --body x", "issue_write"),
        ("npx -y -p gh gh issue edit 5 --body x", "issue_write"),
        ("printf '%s' x | xargs -I{} gh issue edit {} --body {}", "issue_write"),
        ("echo 5 | xargs -n 1 gh pr edit --body x", "update_pull_request"),
        ("gh -R x/opencloudtouch issue edit 5 --body x", "issue_write"),
        ("gh pr view 5 --json body -q .body | gh pr edit 5 --body-file -", "update_pull_request"),
    ],
)
def test_bash_gh_and_api_calls_are_routed(command, route):
    d = decide("Bash", {"command": command}, HookContext())
    assert d.action == "deny", command
    assert route in d.reason and "Allowed route" in d.reason


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'gh issue edit 42 --body x'",
        "gh issue view 42",
        "gh pr list --state open",
        "gh issue edit 42 --add-label ux --title t",
        "gh pr checks 7",
        "gh api repos/o/opencloudtouch/issues/42",
        "gh api graphql -f query='{ repository { name } }'",
        "gh issue edit 42 -R someone/other --body x",
        "curl -s https://api.github.com/repos/o/opencloudtouch/issues/42",
        "curl -X POST https://example.com/issues -d x",
        "npm test && pytest -q",
        "echo 'unbalanced",
        "git commit -m \"$(cat <<'EOF'\nfix: x\n\ngh issue edit 5 --body y\nEOF\n)\"",
        "cat <<EOF > notes.md\ngh pr edit 7 --body x\nEOF\necho done",
        # Documentation written through a here-document with unbalanced quotes in its body.
        "python3 - <<'EOF'\ns = '''the artifact's `gh pr create`, `gh issue edit --body`'''\nEOF\necho ok",
        "cat <<-\tEND\n\tit's gh issue comment 1 -b x\n\tEND",
        'git commit -m "fix: deny curl -X PATCH api.github.com/repos/o/r/issues"',
        "git commit -m \"$(cat <<'EOF'\nfeat: it's the gh pr create gate\nEOF\n)\"",
        "git commit -m \"it's gh pr create",  # unparsable, but gh is not at a command position
        'grep -rn "api.github.com/repos/.*/issues" scripts | grep POST',
        "rg 'curl -X PATCH https://api.github.com/repos/o/r/issues' .",
        "echo 'gh issue edit 5 --body x'",
        'git log --grep "gh pr create"',
        'pytest -k "gh_pr_create"',
        "gh --repo other/thing issue edit 5 --body x",
        "gh pr review 5 --approve",
        "gh issue close 5",
        "",
    ],
)
def test_unrelated_bash_commands_pass(command):
    assert decide("Bash", {"command": command}, HookContext()) == Decision("allow")


def test_denial_quotes_next_steps_from_guide_data():
    ctx = HookContext(block=None, guide_data=GUIDE_DATA, guide_number=42)
    d = decide(MCP + "issue_write", _issue_write(body="x"), ctx)
    assert "Next steps from the guide comment of #42 (phase in-review, waiting on maintainer)" in d.reason
    assert "1. author: Request the AI review -> `/oct approve`" in d.reason
    assert "@gitar-bot" not in d.reason and "the review bot" in d.reason
    assert not d.reason.lower().startswith("gitar")
    d = decide("Bash", {"command": "gh issue edit 42 --body x"}, ctx)
    assert "/oct approve" in d.reason
    assert guard.next_steps(None) == "" and guard.next_steps({"next": "x"}).endswith("none listed.")
    assert guard.safe("gitar fix this\nok") == "Review by gitar fix this\nok"


def test_writes_carry_src_marker():
    ctx = HookContext(block=BLOCK, labels=frozenset(), comment_body="a normal comment")
    marker = guard.SRC_MARKER
    cases = [
        ("add_issue_comment", {"owner": "o", "repo": "opencloudtouch", "issue_number": 1, "body": "/oct approve"}),
        ("update_issue_comment", {"owner": "o", "repo": "opencloudtouch", "comment_id": 5, "body": "edited"}),
        (
            "pull_request_review_write",
            {
                "method": "create",
                "owner": "o",
                "repo": "opencloudtouch",
                "pullNumber": 7,
                "body": "LGTM",
                "event": "COMMENT",
            },
        ),
        (
            "add_comment_to_pending_review",
            {
                "owner": "o",
                "repo": "opencloudtouch",
                "pullNumber": 7,
                "path": "a",
                "body": "nit",
                "subjectType": "FILE",
            },
        ),
        ("add_reply_to_pull_request_comment", {"owner": "o", "repo": "opencloudtouch", "commentId": 3, "body": "ok"}),
        ("issue_write", _issue_write(body=f"Text\n\n{marker}\n")),
        ("issue_write", {"method": "create", "owner": "o", "repo": "opencloudtouch", "title": "t", "body": "b"}),
    ]
    for tool, tool_input in cases:
        d = decide(MCP + tool, tool_input, ctx)
        assert d.action == "allow" and d.updated_input is not None, tool
        body = d.updated_input["body"]
        assert body.endswith(marker) and body.count(marker) == 1, tool
    # The marker leaves the block (hash) and a CRLF body intact.
    body = decide(MCP + "issue_write", _issue_write(body="a\r\nb"), ctx).updated_input["body"]
    assert render.extract_block(body) == BLOCK and body.endswith("a\r\nb\r\n\r\n" + marker)
    # A reaction without body, an unrelated tool or another repository is left alone.
    reaction = {"owner": "o", "repo": "opencloudtouch", "issue_number": 1, "reaction": "+1"}
    assert decide(MCP + "add_issue_comment", reaction, ctx) == Decision("allow")
    assert decide(MCP + "list_issues", {"owner": "o", "repo": "opencloudtouch"}, ctx) == Decision("allow")
    other = {"owner": "o", "repo": "elsewhere", "issue_number": 1, "body": "x"}
    assert decide(MCP + "add_issue_comment", other, ctx) == Decision("allow")
    assert guard.with_marker("") == marker


def test_session_start_injects_block_and_guide_data(tmp_path):
    api = FakeApi(
        {42: {"title": "feat: hooks @gitar-bot", "body": f"{BLOCK}\n\nText", "labels": []}}, {42: _guide_body()}
    )
    out = io.StringIO()
    env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
    with GitStub("https://github.com/opencloudtouch/opencloudtouch.git", "feat/42-hooks"):
        assert session_start.main(io.StringIO("{}"), out, env, lambda o, r: api) == 0
    payload = json.loads(out.getvalue())["hookSpecificOutput"]
    assert payload["hookEventName"] == "SessionStart"
    text = payload["additionalContext"]
    assert BLOCK in text and "/oct approve" in text and '"phase": "in-review"' in text
    assert "#42 (from branch feat/42-hooks)" in text and "@gitar-bot" not in text
    assert "Never edit the oct-status block" in text
    # The block and the guide data are fenced and marked as untrusted data.
    assert "untrusted" in text and f"~~~markdown\n{BLOCK}\n~~~" in text and "~~~json\n" in text


@pytest.mark.parametrize(
    ("branch", "number"),
    [
        ("feat/42-hooks", 42),
        ("fix/7", 7),
        ("docs/2026-10-30-oct-status-plan", None),  # a date, not an artifact
        ("feat/1234567-x", None),
        ("main", None),
        ("feat/hooks-42", None),
    ],
)
def test_session_start_branch_numbers(branch, number):
    match = session_start._BRANCH_NUMBER.match(branch)
    assert (int(match[1]) if match else None) == number


# --- Session start: other paths ------------------------------------------------------------------------


class FakeApi:
    def __init__(self, issues: dict, guides: dict | None = None, pulls: dict | None = None, fail: bool = False):
        self.issues, self.guides, self.pulls, self.fail = issues, guides or {}, pulls or {}, fail
        self.calls: list[str] = []

    def _check(self, what: str) -> None:
        self.calls.append(what)
        if self.fail:
            raise rest.RestError("offline")

    def issue(self, number: int) -> dict:
        self._check(f"issue {number}")
        if number not in self.issues:
            raise rest.RestError("404")
        return self.issues[number]

    def guide_comment(self, number: int) -> dict | None:
        self._check(f"guide {number}")
        body = self.guides.get(number)
        return {"body": body} if body else None

    def comment(self, comment_id: int) -> dict:
        self._check(f"comment {comment_id}")
        return {"body": "plain"}

    def open_pull_for_head(self, branch: str) -> int | None:
        self._check(f"pulls {branch}")
        return self.pulls.get(branch)


class GitStub:
    """Replaces `subprocess.run` in rest for git calls."""

    def __init__(self, remote: str | None, branch: str | None):
        self.remote, self.branch = remote, branch

    def __call__(self, args, **kwargs):
        class Done:
            returncode = 0
            stdout = ""

        done = Done()
        if args[:3] == ["git", "remote", "get-url"]:
            done.stdout = self.remote or ""
        elif args[:2] == ["git", "rev-parse"]:
            done.stdout = self.branch or ""
        else:
            done.returncode = 1
        return done

    def __enter__(self):
        self._saved = rest.subprocess.run
        rest.origin_repo.__defaults__ = (self,)
        rest.current_branch.__defaults__ = (self,)
        return self

    def __exit__(self, *exc):
        rest.origin_repo.__defaults__ = (self._saved,)
        rest.current_branch.__defaults__ = (self._saved,)


def _session(api, remote="https://github.com/o/opencloudtouch", branch="main") -> str:
    out = io.StringIO()
    with GitStub(remote, branch):
        assert session_start.main(io.StringIO("{}"), out, {"CLAUDE_PROJECT_DIR": "."}, lambda o, r: api) == 0
    return json.loads(out.getvalue())["hookSpecificOutput"]["additionalContext"]


def test_session_start_uses_the_pull_request_of_the_branch():
    api = FakeApi({7: {"title": "t", "body": "no block", "labels": []}}, {7: _guide_body() + BLOCK}, {"claude/x": 7})
    text = _session(api, branch="claude/x")
    assert "the open pull request of branch claude/x" in text and BLOCK in text  # Dependabot: block in the guide


def test_session_start_falls_back_to_the_static_rules():
    assert _session(FakeApi({}), branch="main") == guard.safe(session_start.RULES)  # no PR for main
    assert _session(FakeApi({}), remote=None, branch="feat/1-x") == guard.safe(session_start.RULES)
    assert _session(FakeApi({}), branch=None) == guard.safe(session_start.RULES)
    text = _session(FakeApi({}, fail=True), branch="feat/9-x")
    assert "#9 (from branch feat/9-x): its status could not be read" in text
    assert _session(FakeApi({}, fail=True), branch="claude/x") == session_start.RULES  # error: still exit 0
    text = _session(FakeApi({3: {"title": "t", "body": "", "labels": []}}), branch="fix/3")
    assert "no guide comment data yet" in text and "no status block yet" in text
    out = io.StringIO()
    assert session_start.main(io.StringIO("not json"), out, {}, lambda o, r: None) == 0


# --- Guard wrapper ---------------------------------------------------------------------------------------


def _run_guard(event: dict, api=None, project: Path = ROOT) -> tuple[int, dict | None, str]:
    out, err = io.StringIO(), io.StringIO()
    env = {"CLAUDE_PROJECT_DIR": str(project)}
    with GitStub("git@github.com:opencloudtouch/opencloudtouch.git", "main"):
        code = guard.main(io.StringIO(json.dumps(event)), out, err, env, lambda o, r: api)
    return code, (json.loads(out.getvalue()) if out.getvalue() else None), err.getvalue()


def test_guard_main_splices_through_rest():
    api = FakeApi({42: {"body": f"{BLOCK}\nold", "labels": [{"name": "spec"}]}})
    event = {"tool_name": MCP + "issue_write", "tool_input": _issue_write(body="new"), "permission_mode": "default"}
    code, answer, _ = _run_guard(event, api)
    assert code == 0 and answer is not None
    hso = answer["hookSpecificOutput"]
    assert hso["permissionDecision"] == "ask" and hso["updatedInput"]["body"].startswith(BLOCK + "\n\nnew")
    code, answer, _ = _run_guard({**event, "permission_mode": "bypassPermissions"}, api)
    assert answer["hookSpecificOutput"]["permissionDecision"] == "allow"
    # Every other mode, also an unknown or missing one, shows the rewritten call to the user.
    for mode in ("acceptEdits", "dontAsk", "plan", "auto", "something-new", None):
        _, answer, _ = _run_guard({**event, "permission_mode": mode}, api)
        assert answer["hookSpecificOutput"]["permissionDecision"] == "ask", mode
    # Artifact without a block (not backfilled, Dependabot): only the marker.
    api = FakeApi({42: {"body": "plain", "labels": []}})
    _, answer, _ = _run_guard(event, api)
    assert answer["hookSpecificOutput"]["updatedInput"]["body"] == "new\n\n" + guard.SRC_MARKER


def test_guard_main_denies_offline_and_quotes_guide():
    event = {
        "tool_name": MCP + "update_pull_request",
        "tool_input": {"owner": "o", "repo": "opencloudtouch", "pullNumber": 7, "body": "x"},
    }
    code, answer, _ = _run_guard(event, FakeApi({}, {7: _guide_body()}))
    hso = answer["hookSpecificOutput"]
    assert code == 0 and hso["permissionDecision"] == "deny" and "/oct approve" in hso["permissionDecisionReason"]
    bash = {"tool_name": "Bash", "tool_input": {"command": "gh pr edit 7 --body x"}}
    _, answer, _ = _run_guard(bash, FakeApi({}, {7: _guide_body()}))
    assert "/oct approve" in answer["hookSpecificOutput"]["permissionDecisionReason"]
    _, answer, _ = _run_guard(bash, None)  # no API at all: denial without steps
    assert answer["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert _run_guard({"tool_name": "Bash", "tool_input": {"command": "ls"}}) == (0, None, "")


def test_guard_main_pr_creation_and_comment_edit():
    spec = {
        "title": "[Spec]",
        "body": "## Definition of Ready\n- [x] a\n",
        "labels": [{"name": "spec"}, {"name": "phase:ready"}],
    }
    api = FakeApi({537: spec}, pulls={"feat/560": 560})
    event = {"tool_name": MCP + "create_pull_request", "tool_input": _create(_pr_body(), base="feat/560")}
    _, answer, _ = _run_guard(event, api)
    assert answer["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "pulls feat/560" in api.calls
    _, answer, _ = _run_guard(event, api, project=Path("/nonexistent"))  # template unreadable
    assert answer["hookSpecificOutput"]["permissionDecision"] == "deny"
    edit = {
        "tool_name": MCP + "update_issue_comment",
        "tool_input": {"owner": "o", "repo": "opencloudtouch", "comment_id": 5, "body": "x"},
    }
    _, answer, _ = _run_guard(edit, api)
    assert answer["hookSpecificOutput"]["permissionDecision"] == "ask"
    _, answer, _ = _run_guard(edit, FakeApi({}, fail=True))
    assert answer["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_guard_main_fails_closed_on_internal_error(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr(guard, "decide", boom)
    code, answer, err = _run_guard({"tool_name": MCP + "add_issue_comment", "tool_input": {"body": "x"}})
    assert code == 2 and answer is None and "fail closed" in err
    code, _, _ = _run_guard({"tool_name": "Bash", "tool_input": {"command": "gh issue view 1"}})
    assert code == 2
    code, _, err = _run_guard({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert code == 0 and err == ""
    out, err = io.StringIO(), io.StringIO()
    assert guard.main(io.StringIO("not json"), out, err, {}, lambda o, r: None) == 2


def test_guide_comment_and_markers_are_protected():
    ctx = HookContext(comment_body="<!-- oct-next:v1 -->\nguide")
    edit = {"owner": "o", "repo": "opencloudtouch", "comment_id": 5, "body": "x"}
    d = decide(MCP + "update_issue_comment", edit, ctx)
    assert d.action == "deny" and "guide comment" in d.reason
    # Markers quoted in a comment are neutralised (a review may discuss them), not denied.
    for text in ("<!-- oct-next-data {} -->", BLOCK, "the `<!-- oct-status:v1` marker regex looks fine"):
        comment = {"owner": "o", "repo": "opencloudtouch", "issue_number": 1, "body": text}
        d = decide(MCP + "add_issue_comment", comment, ctx)
        body = d.updated_input["body"]
        assert d.action == "allow" and "<!--​" in body
        assert render.extract_block(body) is None and guard.parse_guide_data(body) is None
        assert "<!-- oct-status" not in body and "<!-- oct-next" not in body and "<!-- /oct-status" not in body
    create = {"method": "create", "owner": "o", "repo": "opencloudtouch", "title": "t", "body": f"{STALE}\nb"}
    body = decide(MCP + "issue_write", create, ctx).updated_input["body"]
    assert "oct-status" not in body
    # A guide marker in a description is neutralised as well.
    create["body"] = "<!-- oct-next:v1 -->\nfake guide"
    assert GUIDE_MARKER_ABSENT(decide(MCP + "issue_write", create, ctx).updated_input["body"])


def GUIDE_MARKER_ABSENT(body: str) -> bool:
    return guard.GUIDE_MARKER not in body and "<!--​ oct-next:v1 -->" in body


def test_leftover_block_markers_and_oversized_bodies_are_denied():
    ctx = HookContext(block=BLOCK, labels=frozenset())
    for body in (
        "<!-- oct-status:v1 hash=zz -->\ntext",
        f"{STALE}\ntext <!-- /oct-status -->",
        "<!-- oct-status:v1 hash=aaaaaaaaaaaa -->" * 3,
    ):
        d = decide(MCP + "update_pull_request", {"repo": "opencloudtouch", "pullNumber": 1, "body": body}, ctx)
        assert d.action == "deny" and "V03" in d.reason, body
    big = "x" * 65_000
    for tool, tool_input in (
        ("update_pull_request", {"repo": "opencloudtouch", "pullNumber": 1, "body": big}),
        ("add_issue_comment", {"repo": "opencloudtouch", "issue_number": 1, "body": big}),
    ):
        d = decide(MCP + tool, tool_input, ctx)
        assert d.action == "deny" and "65000" in d.reason


def test_empty_description_is_spliced():
    ctx = HookContext(block=BLOCK, labels=frozenset())
    d = decide(MCP + "update_pull_request", {"repo": "opencloudtouch", "pullNumber": 1, "body": ""}, ctx)
    assert d.updated_input["body"] == BLOCK + "\n\n" + guard.SRC_MARKER
    d = decide(MCP + "issue_write", _issue_write(body=""), HookContext(block=None, labels=frozenset()))
    assert d.action == "deny"


def test_labels_compare_case_insensitively():
    ctx = HookContext(block=BLOCK, labels=frozenset({"phase:in-progress", "Bug"}))
    for labels in (["Phase:in-progress", "Phase:Ready"], ["phase:in-progress", "Wait:Maintainer"], [" phase:ready "]):
        assert decide(MCP + "issue_write", _issue_write(labels=labels), ctx).action == "deny", labels
    assert decide(MCP + "issue_write", _issue_write(labels=["PHASE:IN-PROGRESS ", "bug"]), ctx).action == "allow"
    for command in ("gh issue edit 5 --add-label Phase:ready", 'gh issue edit 5 --add-label " phase:ready"'):
        assert decide("Bash", {"command": command}, ctx).action == "deny", command


def test_invalid_owner_or_repo_fails_closed():
    bad = {"owner": "o/../x", "repo": "opencloudtouch", "issue_number": 1, "body": "x"}
    assert decide(MCP + "add_issue_comment", bad, HookContext()).action == "deny"
    assert guard.needs_for(MCP + "add_issue_comment", bad) == guard.Needs()
    with pytest.raises(rest.RestError):
        rest.Rest("o", "a b")
    assert rest.factory({"GH_TOKEN": "t"}, 0.0)("o", "x/y") is None


def test_long_commands_and_heredocs_stay_fast():
    import time

    for command in ("<<A\n" * 25_000, "gh x <<A\n" * 25_000, "a" * 100_000, "$(" * 50_000, "x$(y " * 20_000):
        start = time.monotonic()
        decide("Bash", {"command": command}, HookContext())
        guard._decide_bash(command[:32_000], HookContext())
        guard._drop_heredoc_bodies(command)
        assert time.monotonic() - start < 2, command[:10]
    d = decide("Bash", {"command": "gh issue view 1 " + "x" * 40_000}, HookContext())
    assert d.action == "deny" and "longer than" in d.reason
    assert decide("Bash", {"command": "echo " + "x" * 40_000}, HookContext()).action == "allow"
    # Several here-documents on one line, and a second one that never ends.
    text = "cat <<A <<B\nit's\nA\nit's\nB\ngh issue edit 1 --body x"
    assert decide("Bash", {"command": text}, HookContext()).action == "deny"
    text = "cat <<A <<B\nx\nA\ngh issue edit 1 --body x\nA"
    assert decide("Bash", {"command": text}, HookContext()).action == "deny"


def test_pull_request_spec_reference_limits():
    gate = MCP + "create_pull_request"
    many = _pr_body(" ".join(f"Part of #{n}" for n in range(1, 7)))
    d = decide(gate, _create(many), PR_CTX)
    assert d.action == "deny" and "split the references" in d.reason
    assert guard.needs_for(gate, _create(many)).specs == ()
    # `/oct no-spec` does not exempt a referenced spec from the readiness check.
    draft = replace(PR_CTX, specs=(SpecInfo(537, phase=Phase.DRAFT),))
    body = _pr_body() + "\n/oct no-spec trivial\n"
    assert decide(gate, _create(body), draft).action == "deny"
    assert decide(gate, _create(body, title="docs: x"), draft).action == "deny"


# --- Parity with the automation (the hooks carry stdlib-only copies) -------------------------------------


def test_copies_match_the_automation():
    cfg = load_config(Path(rules.__file__).with_name("config.yml"))
    assert rest.BOT_LOGINS == frozenset(cfg.bot_logins)
    assert guard.FACT_LABELS == violations.FACT_LABELS
    assert guard.GUIDE_MARKER == rest.GUIDE_MARKER
    body = f"intro\r\n{BLOCK}\n\nrest {STALE}"
    assert guard.extract_block(body) == render.extract_block(body)
    assert guard.splice("Text\n", BLOCK) == render.splice_block("Text\n", BLOCK)
    assert guard.splice(f"{STALE}\r\nText", BLOCK) == render.splice_block(f"{STALE}\r\nText", BLOCK)
    assert guard.template_keys(TEMPLATE) == violations.template_keys(TEMPLATE)
    for body in (
        "",
        "## Definition of Ready\n- [x] a\n- [ ] b n/a\n",
        "## Definition of Ready\n- [ ] a\n",
        "### Definition of Ready\n\n## Next\n- [ ] x",
    ):
        complete, open_items = rules.dor_status(body)
        expected = None if open_items == [rules.DOR_MISSING] else complete
        assert guard.dor_complete(body) == expected, body
    assert guard.parse_guide_data(_guide_body()) == GUIDE_DATA
    assert guard.parse_guide_data("<!-- oct-next-data [1] -->") is None
    assert guard.parse_guide_data("<!-- oct-next-data {x -->") is None


def test_copied_patterns_and_sets_are_identical():
    import yaml

    from oct_status import commands, guide

    assert guard.CHORE_TYPES == frozenset(rules._CHORE_TYPES)
    assert guard.READY_OR_LATER == frozenset(p.value for p in rules._READY_OR_LATER)
    for name in ("_CONVENTIONAL", "_HEADING", "_ITEM", "_NOT_APPLICABLE"):
        mine, theirs = getattr(guard, name), getattr(rules, name)
        assert (mine.pattern, mine.flags) == (theirs.pattern, theirs.flags), name
    for name in ("_HEADING", "_ITEM"):
        assert getattr(guard, name).pattern == getattr(render, name).pattern, name
    assert (guard._BLOCK.pattern, guard._BLOCK.flags) == (render._BLOCK.pattern, render._BLOCK.flags)
    assert guard._BOT.pattern == guide._BOT.pattern and guard._LEADING.pattern == guide._LEADING.pattern
    # Every command a label route names exists.
    named = {m for route in guard.LABEL_ROUTES.values() for m in re.findall(r"/oct ([a-z][a-z-]*)", route)}
    assert named and named <= commands.COMMANDS
    # Every status label of the taxonomy has a route, is a fact or is a resolution (asked of a maintainer).
    taxonomy = yaml.safe_load((Path(rules.__file__).with_name("labels.yml")).read_text(encoding="utf-8"))
    names = {entry["name"] for entry in taxonomy["labels"]}
    status = {n for n in names if n.startswith(guard.STATUS_PREFIXES)}
    assert status and set(guard.LABEL_ROUTES) <= status and guard.FACT_LABELS <= status
    assert all(n in guard.LABEL_ROUTES or n in guard.FACT_LABELS or n.startswith("resolution:") for n in status)
    # Intended difference: the guard drops every block of an agent's text, render replaces one (count=1).
    two = f"{STALE}\n\n{STALE}\nText"
    assert guard.splice(two, BLOCK).count("oct-status:v1") == 1
    assert render.splice_block(two, BLOCK).count("oct-status:v1") == 2


def test_needs_and_tool_names():
    assert guard.tool_key("mcp__github__create_issue") == "issue_write"
    assert guard.tool_key("Bash") == "Bash"
    n = guard.needs_for(MCP + "issue_write", _issue_write(body="x"))
    assert (n.artifact, n.guide) == (42, 42)
    assert guard.needs_for(MCP + "issue_write", _issue_write(title="x")).artifact is None
    n = guard.needs_for(MCP + "create_pull_request", _create(_pr_body("Part of #537 and Closes #12")))
    assert n.specs == (537, 12) and n.template and n.base == "main"
    assert guard.needs_for(MCP + "update_issue_comment", {"comment_id": "5"}).comment_id == 5
    assert guard.needs_for(MCP + "add_issue_comment", {"issue_number": 3.0}).guide == 3
    assert guard.needs_for(MCP + "list_issues", {}) == guard.Needs()
    assert guard.needs_for("Bash", {"command": "gh pr edit https://github.com/o/r/pull/9 -b x"}).guide == 9
    assert guard.bash_artifact("echo 'x") is None and guard.bash_artifact("gh issue view") is None
    assert guard.write_class(MCP + "issue_write", {}) and not guard.write_class("Bash", {"command": 1})
    assert decide("Bash", {"command": None}, HookContext()) == Decision("allow")
    assert guard._int(True) is None and guard._int("x") is None
    assert guard.output(Decision("allow"), None) is None
    assert guard._phase({"phase:bogus", "phase:ready"}) == Phase.READY and guard._phase(set()) is None


# --- REST client ----------------------------------------------------------------------------------------


def _opener(routes: dict):
    seen: list[tuple[str, dict]] = []

    def open_(url, headers, timeout):
        assert 0 < timeout <= rest.TIMEOUT
        seen.append((url, dict(headers)))
        for key, value in routes.items():
            if url.endswith(key):
                if isinstance(value, Exception):
                    raise value
                status, body = value
                return status, body if isinstance(body, bytes) else json.dumps(body).encode()
        return 404, b""

    return open_, seen


def test_rest_client_reads_and_fails_closed():
    comments = [
        {"user": {"login": "someone"}, "body": "<!-- oct-next:v1 --> fake"},
        {"user": {"login": "oct-support"}, "body": "An answer quoting <!-- oct-next:v1 --> is no guide"},
        {"user": {"login": "oct-support"}, "body": _guide_body()},
    ]
    open_, seen = _opener(
        {
            "/issues/1": (200, {"number": 1}),
            "/issues/1/comments?per_page=100&page=1": (200, comments),
            "/issues/2/comments?per_page=100&page=1": (200, [{"user": {"login": "x"}, "body": ""}] * 100),
            "/issues/2/comments?per_page=100&page=2": (200, []),
            "/issues/comments/5": (200, {"body": "c"}),
            "/pulls?state=open&head=o:feat%2Fx": (200, [{"number": 7}]),
            "/issues/3": (200, b"not json"),
            "/issues/4": OSError("timeout"),
            "/issues/6": (200, []),
        }
    )
    api = rest.Rest("o", "opencloudtouch", "secret-token", open_)
    assert api.issue(1) == {"number": 1}
    assert seen[0][1]["Authorization"] == "Bearer secret-token" and "secret-token" not in seen[0][0]
    assert api.guide_comment(1)["user"]["login"] == "oct-support"
    assert api.guide_comment(2) is None
    assert api.comment(5) == {"body": "c"}
    assert api.open_pull_for_head("feat/x") == 7
    for number in (3, 4, 6, 9):
        with pytest.raises(rest.RestError) as info:
            api.issue(number)
        assert "secret-token" not in str(info.value)
    with pytest.raises(rest.RestError):
        api.comment(9)
    anon = rest.Rest("o", "r", None, open_)
    with pytest.raises(rest.RestError):
        anon.open_pull_for_head("none")
    assert "Authorization" not in seen[-1][1]


def test_rest_client_refuses_redirects_oversize_and_late_requests():
    import time

    open_, seen = _opener({"/issues/1": (301, b""), "/issues/2": (200, b"[" + b" " * rest.MAX_BYTES + b"]")})
    api = rest.Rest("o", "opencloudtouch", "t", open_)
    for number in (1, 2):
        with pytest.raises(rest.RestError):
            api.issue(number)
    late = rest.Rest("o", "opencloudtouch", "t", open_, deadline=time.monotonic() - 1)
    calls = len(seen)
    with pytest.raises(rest.RestError) as info:
        late.issue(1)
    assert "time budget" in str(info.value) and len(seen) == calls  # no request was sent
    # The redirect handler gives urllib nothing to follow.
    assert rest._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example") is None


def test_rest_factory_looks_up_the_token_once():
    import time

    lookups: list[int] = []

    class Done:
        returncode, stdout = 0, "tok"

    def run(*args, **kwargs):
        lookups.append(1)
        return Done()

    make = rest.factory({}, time.monotonic() + 40, run)
    first, second = make("o", "opencloudtouch"), make("o", "other")
    assert first is not None and second is not None and len(lookups) == 1
    assert first.deadline == second.deadline


def test_rest_helpers():
    assert rest.find_token({"GH_TOKEN": " t "}) == "t"

    class Done:
        def __init__(self, code, out):
            self.returncode, self.stdout = code, out

    assert rest.find_token({}, lambda *a, **k: Done(0, "tok\n")) == "tok"
    assert rest.find_token({}, lambda *a, **k: Done(1, "")) is None

    def missing(*a, **k):
        raise FileNotFoundError

    assert rest.find_token({}, missing) is None
    assert rest.origin_repo(Path("."), lambda *a, **k: Done(0, "http://proxy@127.0.0.1:9/git/o/opencloudtouch")) == (
        "o",
        "opencloudtouch",
    )
    assert rest.origin_repo(Path("."), missing) is None
    assert rest.current_branch(Path("."), lambda *a, **k: Done(0, "HEAD")) is None
    assert rest.project_dir({}, {"cwd": "/x"}) == Path("/x")


def test_settings_register_the_hooks():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert set(settings) == {"hooks"}
    pre = settings["hooks"]["PreToolUse"]
    import re

    matchers = [entry["matcher"] for entry in pre]
    assert "Bash" in matchers
    mcp = next(m for m in matchers if m != "Bash")
    for tool in guard.GUARDED_TOOLS:
        assert re.search(mcp, f"mcp__github__{tool}"), tool
    assert not re.search(mcp, "mcp__github__list_issues")
    commands = [h["command"] for entry in pre for h in entry["hooks"]]
    commands += [h["command"] for entry in settings["hooks"]["SessionStart"] for h in entry["hooks"]]
    for command in commands:
        assert command.startswith('python "$CLAUDE_PROJECT_DIR/scripts/oct_status/hooks/')
        assert (ROOT / command.split("$CLAUDE_PROJECT_DIR/")[1].rstrip('"')).is_file()


def test_hook_scripts_run_with_the_standard_library_only(tmp_path):
    """The hooks must start without the automation's dependencies (httpx, PyYAML)."""
    import subprocess
    import sys

    blocker = tmp_path / "sitecustomize.py"
    blocker.write_text(
        "import sys\nclass B:\n    def find_spec(self, name, *a, **k):\n"
        "        if name.split('.')[0] in ('httpx', 'yaml'):\n            raise ImportError(name)\n"
        "sys.meta_path.insert(0, B())\n",
        encoding="utf-8",
    )
    script = ROOT / "scripts" / "oct_status" / "hooks" / "guard.py"
    event = json.dumps({"tool_name": "Bash", "tool_input": {"command": "gh issue edit 1 --body x"}})
    done = subprocess.run(
        [sys.executable, str(script)],
        input=event,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PYTHONPATH": str(tmp_path), "CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": ""},
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    script = ROOT / "scripts" / "oct_status" / "hooks" / "session_start.py"
    done = subprocess.run(
        [sys.executable, str(script)],
        input="{}",
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PYTHONPATH": str(tmp_path), "CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": ""},
        timeout=30,
        check=False,
    )
    assert done.returncode == 0 and "OCT status system" in done.stdout
