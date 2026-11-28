# ADR 009 — DLNA: native presets, speaker as the source of truth

**Date**: 2026-11-26  
**Status**: Accepted  
**Deciders**: OpenCloudTouch maintainers

---

## Context

A SoundTouch speaker plays music from a DLNA/UPnP media server as the source `STORED_MUSIC`. With the
Bose cloud gone, OCT answers the speaker's Marge calls, so registering a media server, storing presets
for it and showing whether it is usable all have to work against OCT.

The first DLNA implementation kept its own copy of the state: presets in the OCT database, a browse
cache, reference presets (`dlna://`) resolved to a first track by OCT, and `Sources.xml` written by
the setup wizard. The copies drifted from what the speaker actually had, and the code was patched
until it was no longer maintainable. The feature was rebuilt from scratch.

Measured on real speakers (firmware 27.0.6):

- The speaker registers a media server itself with `POST :8090/setMusicServiceAccount` and relays
  the registration to Marge as `POST /streaming/account/{account}/source`. Without that route the
  speaker answers error 1022 (`MARGE_SET_CRED_FAILED`). With it, the speaker writes its own
  `Sources.xml` entry and removes it again on `removeMusicServiceAccount`
  (`DELETE /streaming/account/{account}/source/{id}`).
- The speaker stores no source id of its own; it identifies a stored source by type and account
  (`<UDN>/0`). The id comes from the Marge answer.
- A ContentItem stored exactly as the speaker's `/navigate` returns it (no `type` attribute, tracks
  as `<id> TRACK`) behaves the same as an OCT-composed one. A folder whose first child is not audio
  fails to play in both shapes.
- Changing the provider ids in `/full` made the speaker drop its AIRPLAY, QPLAY and SPOTIFY entries
  (those whose id changed); entries with an unchanged id stayed.
- Speaker errors arrive as HTTP 500 with `<errors><error value="...">`. Error 1602 was seen once as a
  transient failure that succeeded on the next request.
- Speaker reads take about 0.1-0.25 s each (`/presets`, `/sources`, `/listMediaServers`,
  `/now_playing`, 10 requests each). Browsing a real media server took 0.6-1.8 s.

---

## Decision

**The speaker is the source of truth.** OCT reads presets, sources and availability live from the
speaker on every request and keeps only what the speaker cannot hold.

| Concern | Choice |
|---------|--------|
| Presets | Native `STORED_MUSIC` presets only. The ContentItem is stored exactly as `/navigate` returned it. No reference mode, no `dlna://`, no first-track resolve, no startup rewrite. |
| Preset slots | `GET /api/presets/{device_id}` answers from OCT's rows at once; a background sync from the speaker's `/presets` publishes the list when it differs. Every OCT preset write and every `presetsUpdated` event publishes the full list as the SSE event `presets`. OCT writes its metadata only after the speaker write succeeded; metadata (logo, artist) is kept while the speaker reports the same location. |
| OCT database | Metadata only: cover, server id and object id (to open the edit dialog at the saved folder), the media-server sources OCT answered as Marge, and the migration version per speaker. |
| Caching | Browse lists are read live and paged. Discovered media servers are cached and rediscovered in the background (a known server is used at once; measured: a blocking discovery cost 5 to 6 s before every browse). Preset rows and now-playing are answered from OCT's state and corrected from the speaker in the background and by its events (amended 2026-11-28 after maintainer tests). |
| Registration | The Bose way: per server through the speaker's own `setMusicServiceAccount` / `removeMusicServiceAccount`. OCT implements the Marge routes the speaker relays (`POST`/`DELETE .../source`, `GET .../sources`), assigns the source ids and stores them per Marge account and server. The UDN is kept exactly as the speaker spells it. OCT never writes `Sources.xml` for this feature. |
| `sourcesUpdated` | After each source change OCT sends `<updates deviceID="..."><sourcesUpdated/></updates>` to the speaker (`POST :8090/notification`), best effort. |
| Provider ids | In `/full` and `GET .../sources` a registered media server uses the same `STORED_MUSIC` provider id as the speaker's default source list: the old id (50) while the speaker's migration version is 0, the catalogue id 7 from version 1 (serving 7 on version 0 made the speaker file the server as `INVALID_SOURCE`). Only the `POST .../source` answer always says `sourceProviderID` 7. The other default sources keep their old provider ids while the migration version is 0. |
| Migration service | Each speaker has a migration version (table `speaker_migrations`, no row = 0). The service runs at startup for every known speaker and again when an offline speaker comes back. Steps are ordered, idempotent and logged per speaker; a failed step leaves the old version and disables the DLNA feature for that speaker. The step 0 -> 1 (switch to the catalogue provider ids) is not registered yet, so every speaker stays on version 0. |
| Availability | A server is `ready` when the speaker lists it as READY in `/sources`, it is in `/listMediaServers` and a browse of its root succeeds; `not_enabled` when OCT has no source for it; otherwise `unavailable`. Error 1602 is retried once. No re-pair loop. |
| Folder check | Saving a folder whose first child is not audio returns 409 `dlna_folder_no_audio_first`; the user can confirm and save anyway. |
| Removing a server | If presets use it, OCT answers 409 with the affected slots read live from the speaker; "remove anyway" removes the source and keeps the presets (pressing them then fails with a speaker error). |
| Playback feedback | Speaker errors (`errorUpdate`) are forwarded as `source_error` events. Now-playing is matched to a preset by ContentItem location and source account, never by name. Shuffle and repeat are read from the speaker and set with its keys. |

---

## Alternatives Considered

### 1. OCT database as the truth, with a cache of the speaker

The previous implementation. Every write had to be mirrored both ways, and every mismatch (a preset
changed on the speaker, a server registered outside OCT) showed wrong state.

**Rejected**: the copies drifted; the measured read latency does not justify a cache.

### 2. Reference presets (`dlna://`) resolved by OCT

OCT stores a reference and turns it into a playable item when the preset is pressed or at startup.

**Rejected**: the speaker cannot play the preset without OCT, and the speaker's own ContentItem
works the same way (measured).

### 3. Writing `Sources.xml` directly over SSH

**Rejected**: needs root access to the speaker, bypasses the speaker's own bookkeeping, and the
speaker writes the entry itself once the Marge route exists.

### 4. Switching all provider ids to the Bose catalogue at once

**Rejected**: measured to drop AIRPLAY, QPLAY and SPOTIFY from the speaker. The switch waits for a
migration step that keeps them.

---

## Consequences

### Positive

- What OCT shows is what the speaker has; presets, sources and availability cannot drift.
- Presets play without OCT's help once stored; they are the speaker's own items.
- Later changes that need a speaker-side change (provider ids, a shared Marge account) have one
  place to run: the migration service.

### Negative / Trade-offs

- Every preset list, server list and browse costs speaker requests (each about 0.1-0.25 s; a browse
  of a real server 0.6-1.8 s).
- With the speaker offline, OCT shows the stored preset rows only; availability cannot be shown.
- OCT cannot fix a media server the speaker does not see (error 1608, see
  [Troubleshooting](../TROUBLESHOOTING.md#dlna-error-1608--server-not-available)); it can only
  explain it.

### Verified on hardware

- **Registration answer shape:** the speaker accepts
  `<source><sourceID>N</sourceID><sourceProviderID>7</sourceProviderID><createdOn/><updatedOn/></source>`
  (201, no error 1022 `MARGE_SET_CRED_FAILED`), writes its own `STORED_MUSIC` entry with the UDN in
  its own spelling and reports it READY.
- **`sourcesUpdated` with `deviceID`:** answered with HTTP 200 and triggers the speaker's `/full`
  fetch; without `deviceID` the speaker answers error 1019 `CLIENT_XML_ERROR`.
- **Native presets in `/full`:** served as `STORED_MUSIC` items with their stored location and the
  `{UDN}/0` account, also after the server was removed. A speaker answer 1047
  `SOURCE_ALREADY_REMOVED` to a removal counts as done. Pressing a preset whose server was removed
  ends in `INVALID_SOURCE`, and the app shows "Source not available".

### Not yet verified on hardware

- **Migration step 0 -> 1:** not implemented; how the speaker keeps AIRPLAY, QPLAY and SPOTIFY when
  the provider ids change is still to be researched, so the step stays unregistered.
- **Shared Marge account:** one account for all speakers is not verified on a speaker yet.

---

## References

- [Marge calls observed from SoundTouch speakers](../MARGE-SPEAKER-CALLS.md)
- [ADR 004 — No authentication](004-no-authentication.md) (trusted LAN)
