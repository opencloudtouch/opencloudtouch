# Ideenschmiede

The Ideenschmiede ("idea forge") is where OpenCloudTouch ideas are written down, debated and voted on **before** anyone writes a spec. An idea is not a commitment: it states a problem, a proposal, the options and the open questions. A spec follows only when the maintainers decide to pursue it.

## How it works

| Where | What |
|---|---|
| GitHub Discussions, category **Ideenschmiede** | One discussion per idea. Vote with the upvote button (and 👎 if you disagree), argue in the comments. |
| [`docs/ideenschmiede/ideas/`](ideas/) | The source text of every idea seeded by maintainers. Readable offline and in the Git history. |
| [`docs/ideenschmiede/research/`](research/) | Background research the ideas refer to. |
| Sticky issue **Ideenschmiede** (label `ideenschmiede`) | A table of all ideas with votes, comments and status. Updated by a workflow; do not edit it by hand. |

## Status of an idea

Maintainers set the status by labelling the discussion:

| Label | Meaning |
|---|---|
| *(none)* | Open for debate |
| `idea:accepted` | Will be pursued; a spec issue follows |
| `idea:specced` | A `spec` issue exists (link it in the discussion) |
| `idea:declined` | Decided against; the reasoning stays in the discussion |

## Proposing an idea

Open a discussion in the category **Ideenschmiede** with the form (problem, idea, benefit). No spec, no Definition of Ready needed. Bugs and concrete feature requests still belong in issues.

## For maintainers

- One-time setup: create the discussion category **Ideenschmiede** (format: *Open-ended discussion*) and the four labels above are created by the workflow. GitHub offers no API to create categories.
- `Actions → Ideenschmiede → Run workflow`: `seed` creates the discussions for all files in `ideas/` that have none yet (idempotent via a hidden marker), `sticky` refreshes the overview issue, `both` does both. `dry_run` prints instead of writing.
- The overview also refreshes on discussion events and once a day.
- Idea file format: a front matter block (`id`, `title`, `summary`) followed by Markdown. See `scripts/ideenschmiede/ideas.py`.
