---
id: 002
title: A project board for features and bugs
summary: Show the lifecycle state of every issue and PR on a GitHub Projects board.
---
## Problem

Whether a feature is being specced, built, waiting for hardware verification or released is only visible by opening each issue. Contributors cannot see what is worth picking up, and maintainers lack an overview.

## Idea

A GitHub Projects (v2) board whose columns follow the status system from #584 (`phase:*` labels, `wait:*` for what a ticket is blocked on). Because the status already lives in labels, the board can be filled automatically instead of dragging cards by hand.

## Options

| Option | Effort | Trade-off |
|---|---|---|
| **A.** Built-in project workflows only (auto-add items, set `Status` on open/close/merge) | Low | No label mapping; closed/merged is all it knows |
| **B.** Workflow that mirrors `phase:*` labels into the board's `Status` field | Medium | Needs a token with the `project` scope (not `GITHUB_TOKEN`) |
| **C.** Board is only a view, columns grouped by label | Low | Grouping by label is limited; no custom fields |

## Open questions

- Which columns? A first draft: *Idea → Spec → Ready → In progress → Waiting (review / hardware) → Done*.
- Do ideas from the Ideenschmiede appear on the board, or only accepted ones with a spec?
- Public board for everyone, or maintainers only?
- Who owns the token for option B?

## Dependencies

The status system (#584) should be merged and in write mode first, otherwise the labels are not reliable.
