---
id: 004
title: Recover automatically when a station stops playing
summary: A bounded, opt-in recovery ladder for dead or expired stream URLs.
---
## Problem

When a radio stream dies (expired URL, provider hiccup, speaker stuck), the user has to notice and press play again. OCT only checks stream reachability when a *manual* station is added; there is no recovery path during playback.

## Idea

An **opt-in** recovery that goes from cheap to invasive and stops as soon as playback is confirmed:

1. Read the speaker state again
2. Re-resolve the station URL through the provider
3. Re-select the same source
4. Controlled stop/play

Guard rails: a per-device lock, a cooldown, at most N attempts per hour, never when the user stopped playback on purpose, and **no retry of an ambiguous write**.

## Where the idea comes from

BASSWIESN ships an eight-stage ladder (`recovery.py`) plus a separate opt-in "live radio reconnect" that is deliberately single-shot (at most 3 attempts per hour, 5 min cooldown, never replays old jobs after a restart). Its own docs mark hardware acceptance as still open. See [the research note](../research/basswiesn-comparison.md).

## Options

- **A. Stages 1-2 only** (re-read, re-resolve). Smallest useful slice.
- **B. A + same-source reselect**
- **C. Full ladder.** The upper stages (service restart, reboot) are not proposed.

## Open questions

- How do we detect "stopped by the user" vs "stream died" reliably through the SoundTouch API?
- Which providers hand out URLs that expire at all? (If it is only a few, the idea shrinks.)
- Default off, and where is the switch (per device or global)?

## Risk

Automatic action on a device the user may be controlling from the hardware keys. Needs a conservative default.
