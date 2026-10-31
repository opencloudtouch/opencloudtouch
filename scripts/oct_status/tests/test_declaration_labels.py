"""M5: declaration labels set by hand are checked like the matching `/oct` command (V07 when rejected)."""

from __future__ import annotations

import json
import re
from dataclasses import replace

from oct_status.main import run_event

from .test_backfill import TimelineRepo
from .test_main_events import BOT, ROOT, api_for
from .test_rules import DOR_DONE
from .test_violations_events import ACTIVE, LEDGER, clock


def labeled(number: int, label: str, sender: str) -> dict:
    return {"action": "labeled", "issue": {"number": number}, "label": {"name": label}, "sender": {"login": sender}}


def hand_label(repo: TimelineRepo, number: int, label: str, sender: str) -> dict:
    repo.issues[number]["labels"].append({"name": label})
    repo.label_events.setdefault(number, []).append((label, sender))
    return labeled(number, label, sender)


def spec_repo(author: str = "alice") -> TimelineRepo:
    """A spec in review (declared by the automation), so `ready` is a legal next declaration."""
    repo = TimelineRepo()
    repo.add(5, labels=("spec", "phase:spec-review"), body=DOR_DONE)
    repo.label_events[5] = [("phase:spec-review", BOT)]
    repo.issues[5]["user"] = {"login": author}
    return repo


CFG = replace(ACTIVE, ledger_issue=LEDGER)


async def run(repo: TimelineRepo, event: str, payload: dict, cfg=CFG, dry_run: bool = False) -> None:
    api = api_for(repo)
    assert await run_event(api, cfg, event, payload, dry_run=dry_run, clock=clock) == 0
    await api.aclose()


def deletes(repo: TimelineRepo, number: int, label: str) -> int:
    return repo.writes.count(("DELETE", f"{ROOT}/issues/{number}/labels/{label}"))


def guide(repo: TimelineRepo, number: int) -> str:
    return next((c["body"] for c in repo.comments.get(number, []) if "oct-next:v1" in c["body"]), "")


def open_rules(repo: TimelineRepo, number: int) -> list[str]:
    data = json.loads(re.search(r"<!-- oct-next-data (.*) -->", guide(repo, number))[1])
    return [n["rule"] for n in data.get("notices", []) if not n["resolved"]]


async def test_ready_by_another_reviewer_is_accepted_and_written_again_by_the_automation():
    repo = spec_repo()
    await run(repo, "issues", hand_label(repo, 5, "phase:ready", "bob"))
    assert "phase:ready" in repo.label_names(5) and "phase:spec-review" not in repo.label_names(5)
    assert deletes(repo, 5, "phase:ready") == 1 and repo.label_events[5][-1] == ("phase:ready", BOT)
    assert open_rules(repo, 5) == [] and "phase:ready set by bob" in guide(repo, 5)
    # Later runs trust the label: the latest label event is the automation's.
    await run(repo, "issues", {"action": "edited", "issue": {"number": 5}, "sender": {"login": "carol"}})
    assert "phase:ready" in repo.label_names(5)


async def test_ready_by_the_author_is_removed_and_noticed_as_v07():
    repo = spec_repo()
    await run(repo, "issues", hand_label(repo, 5, "phase:ready", "alice"))
    assert "phase:ready" not in repo.label_names(5) and "phase:spec-review" in repo.label_names(5)
    assert open_rules(repo, 5) == ["V07"] and "v07-invalid-declaration" in guide(repo, 5)
    assert [(e["rule"], e["user"]) for e in repo.ledger()] == [("V07", "alice")]
    # A later valid `/oct ready` resolves the notice (same declaration command).
    from .test_commands import comment_event

    await run(repo, "issue_comment", comment_event(5, "/oct ready --reviewer bob", login="bob"))
    assert "phase:ready" in repo.label_names(5) and open_rules(repo, 5) == []


async def test_ready_out_of_order_is_rejected():
    repo = spec_repo()
    repo.issues[5]["labels"] = [{"name": "spec"}]  # still a draft: `ready` is not a legal declaration yet
    await run(repo, "issues", hand_label(repo, 5, "phase:ready", "bob"))
    assert "phase:ready" not in repo.label_names(5) and open_rules(repo, 5) == ["V07"]


async def test_ready_with_an_incomplete_definition_of_ready_is_rejected():
    repo = spec_repo()
    repo.issues[5]["body"] = "## Definition of Ready\n- [ ] open item\n"
    await run(repo, "issues", hand_label(repo, 5, "phase:ready", "bob"))
    assert "phase:ready" not in repo.label_names(5) and open_rules(repo, 5) == ["V07"]
    assert "open item" in guide(repo, 5)


async def test_triage_needs_the_maintain_role():
    repo = TimelineRepo()
    repo.add(6, labels=("bug",))
    await run(repo, "issues", hand_label(repo, 6, "phase:triaged", "tess"))  # triage role, not maintain
    assert "phase:triaged" not in repo.label_names(6) and "phase:new" in repo.label_names(6)
    assert open_rules(repo, 6) == ["V07"] and "needs maintain access" in guide(repo, 6)
    other = TimelineRepo()
    other.add(6, labels=("bug",))
    await run(other, "issues", hand_label(other, 6, "phase:triaged", "carol"))  # maintain role
    assert "phase:triaged" in other.label_names(6) and other.label_events[6][-1] == ("phase:triaged", BOT)
    assert open_rules(other, 6) == []


async def test_dry_run_reports_and_writes_nothing():
    repo = spec_repo()
    await run(repo, "issues", hand_label(repo, 5, "phase:ready", "alice"), dry_run=True)
    assert repo.writes == [] and "phase:ready" in repo.label_names(5)


async def test_label_declarations_without_a_command_and_bot_labels_are_left_alone():
    repo = TimelineRepo()
    repo.add(7)
    repo.issues[7]["title"] = "[Test] device check"
    await run(repo, "issues", hand_label(repo, 7, "phase:in-progress", "bob"))
    assert "phase:in-progress" in repo.label_names(7) and deletes(repo, 7, "phase:in-progress") == 0
    assert "v07-" not in guide(repo, 7)
    bot = spec_repo()
    await run(bot, "issues", hand_label(bot, 5, "phase:ready", BOT))  # our own write: ignored
    assert bot.writes == []


async def test_strikes_inactive_still_remove_the_label_with_a_notice():
    repo = spec_repo()
    await run(
        repo, "issues", hand_label(repo, 5, "phase:ready", "alice"), cfg=replace(ACTIVE, strikes_enabled_from=None)
    )
    assert "phase:ready" not in repo.label_names(5) and open_rules(repo, 5) == ["V07"] and repo.ledger() == []


async def test_events_that_are_no_hand_set_declaration_are_skipped():
    repo = TimelineRepo()
    repo.add(8, labels=("enhancement", "phase:confirmed"))  # a feature request has no `confirm`
    await run(repo, "issues", labeled(8, "phase:confirmed", "bob"))
    assert "v07-" not in guide(repo, 8)  # convergence drops the label, it is no declaration of this kind
    gone = spec_repo()
    await run(gone, "issues", labeled(5, "phase:ready", "bob"))  # already removed again
    assert deletes(gone, 5, "phase:ready") == 0 and "v07-" not in guide(gone, 5)
    odd = spec_repo()
    event = hand_label(odd, 5, "phase:ready", "bob")
    event["sender"] = {"login": "not a login"}
    await run(odd, "issues", event)
    # Not checked (no valid sender), so no V07; the hand-set label is not honoured and converges away.
    assert "v07-" not in guide(odd, 5) and "phase:ready" not in odd.label_names(5)
