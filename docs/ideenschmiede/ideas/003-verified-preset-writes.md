---
id: 003
title: Verify preset writes by reading them back
summary: Today a failed preset write is logged and swallowed. Confirm what the speaker actually stored.
---
## Problem

`PresetService.set_preset` saves the preset to the OCT database **first**, then programs the speaker. If programming fails, the error is logged and the call still returns the saved preset (`"Database record is still saved, user can retry"`). The user sees success, and finds out later that the hardware button does nothing. Nothing reads the preset back from the speaker either, so even an HTTP 200 is never confirmed.

(Checked against `apps/backend/src/opencloudtouch/presets/service.py`.)

## Idea

Separate three states and only call the last one success:

1. **sent**: OCT issued the write
2. **accepted**: the speaker answered
3. **confirmed**: OCT read the preset back and it matches

Result values: `CONFIRMED`, `DIVERGED` (speaker reports something else), `UNVERIFIED` (no read-back possible), `REJECTED`. A timeout after a write must **not** trigger a blind retry; read first, the write may have happened.

## Where the idea comes from

BASSWIESN (a community SoundTouch project, MIT licensed) does this with a small state machine `PREPARED → RADIO_WRITE → RADIO_READBACK → VERIFIED → LOCAL_COMMIT` and keeps a hash of the previous and the read-back state. See [the research note](../research/basswiesn-comparison.md). We would take the principle, not the machinery: no durable mutation journal, no rollback.

## Options

- **A. Minimal:** read back once after the write, return the result to the UI, show a warning when not confirmed.
- **B. A + write the DB only after confirmation** (or mark the DB row `pending`).
- **C. Full mutation journal with rollback.** Probably too much.

## Open questions

- How long does a speaker need before `/presets` shows the new value? Needs measuring on real hardware.
- Which fields count as "equal" when the speaker rewrites the XML?
- What does the UI do on `DIVERGED`: offer retry, or show the actual state?

## Hardware

Needs verification on SoundTouch 10/20/30 and one older firmware before any of it is trusted.
