---
id: 005
title: Back off from unreachable devices
summary: Poll offline or flaky speakers less aggressively, with a visible per-device state.
---
## Problem

OCT already reconnects its WebSockets with exponential backoff and runs a 5-minute health check that marks devices offline after 15 minutes. Other paths (zone sync, SSH verify, user-triggered calls) do not share one notion of "this device is currently unreachable", so each retries on its own and logs on its own.

## Idea

A small per-device state (`closed` / `open` / `half-open`, a circuit breaker) that every outgoing device call consults: an unreachable device is probed rarely, battery-powered devices (SoundTouch Portable) even more gently, and the UI can show "unreachable since 10:42" instead of a generic error.

## Where the idea comes from

BASSWIESN `device_policy.py` keeps polling profiles per device class and a circuit state with next-retry times. See [the research note](../research/basswiesn-comparison.md).

## Options

- **A.** Share the existing health-check result with the other callers (no new state machine).
- **B.** Real circuit breaker in the device client layer.
- **C.** Leave as is until there is a reported problem.

## Open questions

- Is there a concrete bug report behind this, or is it theoretical? If nobody is affected, C is the honest answer.
