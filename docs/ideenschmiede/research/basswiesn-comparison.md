# BASSWIESN compared with OpenCloudTouch

Status: 2026-11-02. Based on a shallow clone of `Zimbo88/BASSWIESN` (13 commits, `main` at "BASSWIESN 3.0.2") and of this repository. Nothing here was run on a speaker; BASSWIESN's own hardware claims are reported as claims.

## What was checked

- Repository layout, size, licence, commit history and ignore files of BASSWIESN.
- The modules relevant to stability: `preset_transactions.py`, `recovery.py`, `live_radio_reconnect.py`, `device_policy.py`, `support_export.py`, `playback_keepalive.py`, `stream_compat.py`.
- The OCT counterparts: `presets/service.py`, `devices/health_check.py`, `devices/websocket/connection.py`, `api/bug_report.py`, `api/diagnostics.py`.
- An earlier AI-written comparison and concept (from public README files only, no code audit). Where it disagrees with the code, the code wins; see "Corrections".

## Facts about BASSWIESN

| Topic | Finding |
|---|---|
| History | 13 commits between 2026-08-23 and 2026-09-27; last release 3.0.2 |
| Size | about 80,000 lines of Python including about 1,100 test functions (OCT backend: about 2,300 test functions; the totals are not directly comparable) |
| Stack | FastAPI, SQLAlchemy, Jinja2 templates, vanilla JS; **no React frontend**. Ports 1328/1329/1516/1860 |
| Licence | MIT, preceded by a personal note from the author. Code and ideas may be reused with the copyright notice kept |
| Scope | Management, diagnostics and cloud-protocol emulation; AirPlay bridge disabled, DLNA/updater experimental, hardware acceptance for several features "open" in its own `FEATURES.md` |
| Device policy | Critical writes only for an exact allow-list of models and one firmware build; others are read-only |
| Languages | 28 UI locales, partly with English fallback |

## Which AI was used?

Not determinable, and the repository does not claim one. There are no `Co-Authored-By` trailers or AI mentions in the README, `FEATURES.md` or the changelog. The only traces are in ignore files:

- `.gitignore`: `FÜR chatgpt.tar.xz`, `docs/codex_resume.md`, `docs/FORTSETZUNGS_PROMPT.md`, `docs/session_log.md`
- `.dockerignore`: `.codex`

That points to a workflow with OpenAI tools (ChatGPT, Codex) and session-resume notes, but an ignore entry is not proof of what produced the code. `.gitignore` also lists `*cloudtouch-main*/` and `*SoundTouch-main*/`, so the author had other projects' sources locally; nothing from them is committed, and no code copying was investigated.

## Mechanisms worth knowing

**Preset mutation state machine** (`preset_transactions.py`, 124 lines). States `PREPARED → RADIO_WRITE → RADIO_READBACK → VERIFIED → LOCAL_COMMIT`, with `FAILED`, `RECONCILE`, `ROLLBACK`. Stores a SHA-256 of the previous state, the requested state and the read-back state, a revision per button and a `diverged` flag. Local database is committed only after the speaker confirmed.

**Recovery ladder** (`recovery.py`). Stages `READBACK → METADATA_REFRESH → PROVIDER_REFRESH → STREAM_RERESOLVE → SAME_SOURCE_RESELECT → CONTROLLED_STOP_PLAY → LOCAL_SERVICE_RESTART → MANUAL_LAB_RADIO_REBOOT`. Each failure reason has a maximum stage; protected devices and non-LAB mode cap it lower; runs have cooldowns.

**Live radio reconnect** (`live_radio_reconnect.py`). Opt-in per device, single-shot, 3 attempts per hour, 300 s cooldown. Its docstring is explicit: no startup scan, no timer, no volume command, no preset write, **no retry of an ambiguous POST**, restarts never replay old jobs.

**Device policy** (`device_policy.py`). Per-device-class polling profiles (active, idle, standby, portable on battery, offline backoff) and a circuit state with next-retry time.

**Support export** (`support_export.py`). Regex redaction of secrets and IPs, bounded ZIP.

## What OCT already has

| Area | OCT today |
|---|---|
| Preset write | Saves to the database **first**, then programs the speaker. A failure there is logged and swallowed; the call still returns success. **No read-back.** |
| Stream check | `_check_stream_reachable` only for `manual-` stations at preset time. No re-resolve during playback. |
| Reconnect | WebSocket reconnect with exponential backoff and jitter (`devices/websocket/connection.py`) |
| Health | 5-minute ping, offline after 15 minutes, SSH verify every 30 minutes, zone sync every 15 minutes (`devices/health_check.py`) |
| Support | Bug report endpoint creating a GitHub issue with logs and anonymised IPs; diagnostics download (`api/bug_report.py`, `api/diagnostics.py`) |

## Corrections to the earlier AI comparison

- It proposed a **support bundle** as a new feature. The export already exists; only classification is missing (idea 006).
- It suggested checking whether OCT reads presets back. It does not, and a failed write is reported as success (idea 003).
- It was unsure whether OCT reconnects with backoff. It does, for WebSockets; the gap is shared state across other callers (idea 005).
- Its table treated multiroom verification as a top-three item. OCT already syncs zones every 15 minutes; nothing found in the code shows a concrete multiroom defect, so it is not proposed.

## Not recommended

The firmware allow-list (it would shrink OCT's supported hardware), host flight recorder, automatic reboots and LAB mode (maintenance cost without a reported OCT problem), and the full mutation journal with rollback.

## Ideas derived

[003 verified preset writes](../ideas/003-verified-preset-writes.md), [004 self-healing streams](../ideas/004-self-healing-streams.md), [005 device polling backoff](../ideas/005-device-polling-backoff.md), [006 structured error codes](../ideas/006-structured-error-codes.md).

## Limits of this research

No hardware, no network traces, no execution of either project. Whether BASSWIESN's mechanisms work better in practice is unverified; its documentation itself separates "software-tested" from "hardware-validated".
