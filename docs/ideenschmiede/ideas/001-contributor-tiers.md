---
id: 001
title: Contributor tiers for third-party PRs
summary: The welcome check repeated itself for returning contributors. A first fix landed; should we go further?
---
## Problem

The welcome comment on third-party PRs repeated the first-time text on every PR, because the first-PR detection looked at the wrong PRs (fixed in #597).

## What is in place now

- GitHub's own repository setting holds CI for first-time contributors until a maintainer approves the run **once**.
- Authors with at least one merged PR get a short message and the label `contributor:trusted`.

## Idea: what could come next

1. **Higher threshold.** The original thought was to approve the first 2-3 PRs by hand. GitHub's setting only knows "first-time", so a threshold of 3 needs our own gate on `pull_request_target`, which is itself an attack surface.
2. **Use the label.** `contributor:trusted` could drive other things: skip the bot's "please add tests" nudges, request review faster, or show up in the Community Spotlight.
3. **Do nothing more.** The current behaviour may simply be enough.

## Open questions

- Is one manual approval enough, or do we want more friction for new contributors?
- Should the label be removed after long inactivity, or is it permanent?

## Not in scope

Changing who may merge. Reviews and the Definition of Done stay the same for everyone.
