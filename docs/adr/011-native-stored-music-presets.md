# ADR 011 — Native STORED_MUSIC presets with explicit per-speaker enabling

**Date**: 2026-11-16
**Status**: Accepted
**Deciders**: OpenCloudTouch maintainers

---

## Context

[ADR 009](009-dlna-preset-reference-resolved-at-press-time.md) stores a DLNA preset as a reference that OpenCloudTouch resolves at press time. A folder then plays its first track only, there is no queue, and nothing plays while OpenCloudTouch is offline. A hardware spike showed that a speaker can browse and play a media server itself (source `STORED_MUSIC`, account `<server UUID>/0`) with a queue, and keeps playing with OpenCloudTouch switched off, once OpenCloudTouch lists the media server in the Marge account document of that speaker; no call that registers the server on the speaker is needed.

## Options considered

1. **Keep the reference only (ADR 009).** Nothing to enable, but first track only and OpenCloudTouch must run.
2. **List every discovered server for every speaker automatically.** Convenient, but it changes what every speaker offers without being asked.
3. **Explicit per-speaker, per-server enabling; write natively only when the server is `READY` there, otherwise fall back to the reference (chosen).**

## Decision

Option 3. `DlnaNativeService` derives the state of a (speaker, server) pair from OpenCloudTouch's row (the enabled server it lists in `/full`) and the speaker's live source list. `POST /api/presets/dlna` writes a native item (`source="STORED_MUSIC" sourceAccount="<uuid>/0" location="<object id>"`) only for a container whose server is `ready`; every other case is the unchanged v1 write. The database identity does not change (`source='DLNA'`, `dlna://`, `dlna-<hash>`); the new column `presets.native_type` (`dir`/`track`) marks the native ones and `dlna_playback` (`native`/`reference`) tells the client what was written. Native single tracks stay on the reference path behind the constant `NATIVE_TRACK_PRESETS_VERIFIED` until hardware item H1 shows that `<object id> TRACK` works; the suffix helpers already exist behind it. Enabling stores the row and reads the speaker's source list; only when the server is not `READY` yet, OpenCloudTouch pairs the speaker with its own Marge account once again (`setMargeAccount`), which makes the speaker read the account document, and polls for up to 15 s. A speaker is never restarted and a server that is already `READY` is never touched.

## Consequences

- The default stays safe: not enabled, not `ready` or an unreadable state means the first-track behaviour of ADR 009; an unreadable speaker fails like any other speaker write and stores nothing.
- A native preset survives a switched-off OpenCloudTouch, but OpenCloudTouch cannot observe or report native playback failures.
- Disabling a server that native presets use needs `force`, which first rewrites those slots to the reference format.
- Every reader of a DLNA preset keeps treating it as not streamable; a test per consumer runs for the v1 and the native variant.
- Only MP3 and AAC are known to play natively; other formats, folders over 100 tracks and other speaker models are unverified (see [DLNA.md](../DLNA.md)).
