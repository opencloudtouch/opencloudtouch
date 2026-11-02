---
id: 006
title: Stable error codes in bug reports
summary: OCT already builds diagnostics for bug reports; add machine-readable reasons so triage is faster.
---
## Problem

Long free-text bug reports ("a lot of text without clear requirements") are hard to triage. OCT already has a bug report endpoint that attaches logs, anonymises IPs and creates the GitHub issue (`api/bug_report.py`, `api/diagnostics.py`). What is missing is a *classification*: was it the speaker, the radio provider, the stream, or OCT?

## Idea

Introduce a short list of stable reason codes (for example `DEVICE_UNREACHABLE`, `PROVIDER_RESOLUTION_FAILED`, `STREAM_HTTP_403`, `PRESET_READBACK_DIVERGED`) that the backend attaches to its own failures and that the bug report includes automatically. No new service, no dashboard.

## Where the idea comes from

An AI-assisted comparison with BASSWIESN proposed a full support bundle, health dashboard and event ring buffer. Checking the OCT code showed that the export part already exists, so only the codes are new. See [the research note](../research/basswiesn-comparison.md).

## Options

- **A.** Codes in the bug report only.
- **B.** A + show the code in the UI error message so users can quote it.

## Open questions

- Which failures are frequent enough to deserve a code? Start from real issues, not from a catalogue.
- Depends on idea 003: `PRESET_READBACK_DIVERGED` only exists if we verify writes.
