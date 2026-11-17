# Changelog

All notable changes to OpenCloudTouch are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed
- The `metadata_enriched` event no longer replaces the station artwork with an ICY station URL that is not an image (for example a web page); the logo stays instead of switching to the default image. The image-URL check now lives in `core/image_url.py`
- The REST now-playing response no longer takes a non-image ICY station URL as artwork when the speaker reports none
- A web page whose path looks like a logo (for example `/logo-station.html`) is no longer accepted as artwork
- The artwork URL check matches whole path segments, so a path such as `/logout` is no longer taken for a logo
- A DLNA preset keeps its "DLNA" marker, folder/track type and cover when the speaker calls back a preset write with a renumbered media server source id for the same object; "Load from device" keeps the cover and homepage OCT already has when the speaker reports none
- A media server is "ready" (and selectable for presets) only when the speaker lists it as READY and can browse its root through its own `/navigate` (probe cached 60 s, failures 10 s); otherwise it is "unavailable". Before, the READY flag alone was trusted, which showed servers the speaker cannot browse as ready

### Added
- The OpenAPI contract documents `NowPlayingResponse` and `KeyPressResponse` as the response schemas of `GET /api/devices/{device_id}/now-playing` and `POST /api/devices/{device_id}/key`; the change is additive (new `shuffle_setting` and `repeat_setting` fields, nullable)
- The preset dialog opens pre-filled from the saved preset: provider presets show their station name in the search field and search once, manual presets their URL, DLNA presets open the browser in the saved item's folder with the item focused (or the server root / list with a notice when the item or server is gone); stream filters are not restored
- `GET /api/dlna/servers/{server_id}/objects/path?object_id=...` returns the ancestor folders of a saved DLNA object (breadcrumb from the root down to its parent, with `server_name`, `title` and `is_container`), read live in at most 16 levels under one deadline; the preset dialog can use it to open at the saved item
- The DLNA folder browser shows cached listings at once (also the server root), updates stale ones silently after 3 s and 8 s, offers a "Refresh" action that bypasses the backend cache, and prefetches the first page of a folder on mouse hover (200 ms), pointer down or keyboard focus (450 ms) with at most one speculative request at a time and 4 per 10 s; it is off with Save-Data. Listings stay 45 s fresh in the client, items are de-duplicated across pages
- DLNA folder listings are cached in memory and served stale-while-revalidate: a listing answers at once, is refreshed in the background when it is older than `OCT_DLNA_CACHE_TTL` (default 900 s) and is still served up to `OCT_DLNA_CACHE_STALE_TTL` (default 7 days); equal simultaneous requests share one media server request and the cache survives a media server leaving discovery. `GET /api/dlna/servers/{server_id}/browse` gains `refresh` and the response fields `cached`, `cached_at`, `stale` and `revalidating`; `object_id` is limited to 512 characters; `OCT_DLNA_CACHE_MAX_ITEMS` (default 20000) bounds the memory, `OCT_DLNA_CACHE_TTL=0` disables the cache, and `GET /api/diagnostics` shows a `dlna_cache` section with counters and limits
- DLNA browsing is paged: `GET /api/dlna/servers/{server_id}/browse` takes `starting_index` and `requested_count` and returns `number_returned`, `total_matches`, `next_index` and `has_more`; only folders and audio items are listed, and cover URLs that are not absolute http(s) are dropped
- `OCT_DLNA_TIMEOUT` (default 15 s, 1-60) sets the DLNA read timeout and the total deadline per operation; connecting times out after 3 s
- With `OCT_MOCK_MODE=true` a fake "Mock Media Server" (120 tracks, nested folders, mixed content) answers DLNA browsing without network access
- Stereo pairs for SoundTouch 10 (LEFT/RIGHT) can be created, listed, repaired and dissolved from the multi-room page, without SSH access to the speakers
- The speaker-facing Marge emulation answers the group calls (create, read, rename, delete, teardown), `provider_settings` and the recents the speaker reports (`POST .../device/{id}/recent`)
- A stereo pair shows as one device in the device list: the pair name, "2× model", the main speaker's IP, an "L/R Stereo" badge and both speakers in the footer; the second speaker is no longer listed there, and the pair is dissolved from its card (presets stay on the main speaker)
- Group changes on a speaker (`groupUpdated`) are parsed and forwarded as a `group` event on the device event stream; the pair list refreshes on it

- `POST /api/presets/dlna` assigns a DLNA track (or the first track of a folder) to a preset button; OpenCloudTouch stores a reference to the media server object, not a playback URL, and resolves the current URL when the button is pressed, so a new server IP does not break the preset. Preset responses gain a `dlna` field (`{server_id, object_id}` or `null`); new error codes `dlna_not_playable`, `dlna_reference_too_long` and `dlna_preset_not_streamable`
- OpenCloudTouch looks for DLNA media servers once at startup so the first button press can find them
- `GET /api/dlna/servers` answers at once with the servers already known and rescans in the background (`?refresh=true` waits for a fresh scan); the DLNA dialog shows the list immediately, picks up newly found servers a few seconds later and "Search again" waits for a fresh scan
- The preset dialog has a DLNA mode next to TuneIn and RadioBrowser: pick a media server, browse its folders (breadcrumb, paged "Load more", filter over the loaded entries) and put a track or a folder on the preset button; the last folder is remembered for the browser session, and DLNA presets are marked with a DLNA label in the preset list
- The DLNA mode of the preset dialog shows the state of the selected media server on the speaker (Ready, Not set up, Not available, State unknown), sets a server up automatically when you save a folder or track on it (no restart, no extra step), lets you remove a media server with the list of presets that will be switched, and lists servers that are no longer found. Folder rows read "Plays as a folder"

- The Marge emulation lists enabled DLNA media servers as native `STORED_MUSIC` sources: per-server sources in `/full` (provider id 7), the new handshake route `POST /streaming/account/{id}/device/` used when a speaker is re-paired, and the speaker's numeric source ids are mapped back to `STORED_MUSIC` when it reports presets and recents; a new table `media_server_sources` and a `presets.native_type` column are added by migration (downgrade is not supported)

- Native playback of a media server on a speaker: `GET /api/dlna/native`, `GET /api/dlna/native/{device_id}/servers/{server_id}/presets`, `PUT` and `DELETE /api/dlna/native/{device_id}/servers/{server_id}` enable or disable the media server as a speaker source (`STORED_MUSIC`) and report its state from the speaker's live source list. OpenCloudTouch lists the server itself; a speaker that does not list it yet is paired again once (`setMargeAccount`), never restarted; new error codes `dlna_native_in_use`, `dlna_native_setup_failed` and `dlna_native_remove_failed`

- `POST /api/presets/dlna` writes a DLNA folder or a single track as a native `STORED_MUSIC` preset (a folder plays with queue, both play without OpenCloudTouch) when the media server is `ready` on the speaker; otherwise it keeps the first-track reference preset. Preset responses gain `dlna_playback` (`native`, `reference` or `null`) (see ADR 011)

### Changed
- `STORED_MUSIC` is announced with the real provider id 7 instead of 50 in `/streaming/sourceproviders` and `/full` (50 is still accepted from speakers that cached the old list)
- DLNA browse returns 50 entries per request by default instead of the whole folder; DLNA errors carry the codes `dlna_server_not_found`, `dlna_object_not_found`, `dlna_upstream_error` and `dlna_server_timeout` (a slow server now answers 504 instead of 502)
- The failure log line of a DLNA browse request no longer carries the media server id at WARNING level (it reads `DLNA browse failed: <fixed text>`); the server id appears only in a separate DEBUG line

### Fixed
- The "cannot play this item" message of the DLNA preset dialog now explains that a folder which only contains other folders cannot be saved and tells to open one with tracks (for example an album or "All songs"), in all 10 languages
- Dialog accessibility and narrow screens: the active chip keeps a readable check mark in forced-colors (high contrast) mode, the removal dialog starts with the focus on "Cancel", every dialog returns the focus to its opener even when the opener was re-created while the dialog was open, and the "Plays as a folder" hint wraps instead of being cut off at 320 px
- The station logo on the now-playing card no longer falls back to the default image while the station plays: a stream event without a station name (buffering, track update) keeps the current station and its logo
- A DLNA preset slot shows "Playing" or "Paused" while the speaker plays that item: the now-playing response and event stream carry the played item (`content_location`, `item_name`) and `skip_enabled`; previous/next are disabled when the speaker reports no skip (a single track)
- Saving a DLNA preset could fail once with HTTP 500 (`cannot commit transaction - SQL statements in progress`) when it raced a write of the speaker; upserts that return a row now read it in one step
- SSDP discovery (speakers and DLNA media servers) no longer misses servers that run on the same host as OpenCloudTouch (for example a Gerbera container): the search now sends from a private source port instead of the shared port 1900, where the kernel handed unicast replies to an arbitrary socket
- Renaming a stereo pair works: the speaker answers `PUT /updateGroup` with 405, so the rename is sent as `POST /updateGroup` with the whole group
- Every action sent to a speaker (rename, volume, mute, source, key, bass, reboot, preset save/delete, preset load) answers HTTP 503 with code `device_unreachable` and a fixed, readable text (no IP address, no client library text; the details go to the log) when the speaker is offline and changes nothing in OCT; saving a preset no longer succeeds in OCT alone
- Deleting a preset in OCT now also clears the slot on the speaker (HTTP 503 and nothing deleted when the speaker is unreachable), and "Load from device" mirrors the speaker: slots the speaker does not have are removed from OCT.
- Renaming a speaker (from the app or `/name`) works again with the OCT Marge emulation: the speaker's rename call `PUT .../device/{id}` is answered and the new name is stored
- Presets written on the speaker (`PUT/DELETE .../device/{id}/preset/{n}`) are taken over, and `GET .../device/{id}/recents` is answered; the speaker no longer logs 404 for them
- Presets with an unknown source (for example `INTERNET_RADIO`) were missing on the speaker after the account sync change; they are announced as `LOCAL_INTERNET_RADIO` now
- The speaker's account sync (`/streaming/account/{id}/full`) is answered with an `<account>` document; the old `<boseAccount>` root made the speaker fail its sync every minute and broke group creation
- Metadata (title/artist) for TuneIn presets learned from a speaker: the relative station location is resolved to a stream URL before the stream is probed

---

## [2.0.1] - 2026-11-13

### Added
- The `linux/arm/v7` image now starts on ARM NAS devices with a 32 KB memory page size (for example WD My Cloud EX2 Ultra): Debian runtime libraries are rebuilt with 64 KB segment alignment and the entrypoint runs a library self-test instead of rejecting 32 KB kernels. Docker 20.10.9 or newer needs no setting; Docker 19.03.x needs the seccomp profile `seccomp-legacy-docker.json` (attached to every release)
- CI scans the final arm/v7 image for ELF segments that are unsafe on 32 KB pages and runs a QEMU smoke test

---

## [2.0.0] - 2026-11-08

### Added
- Redesigned setup and restore wizards with a shared design, progress tracker, focus management and full keyboard and screen-reader support
- Redesigned app shell, presets page, local control, zones, firmware, settings, diagnostics, about and licenses pages with swipe navigation between devices, a sticky device switch bar and a native `<dialog>` based modal
- Remove button with a confirmation dialog for online and offline devices in presets and local control; saved presets are kept (#520)
- `/health` reports the server `uptime`; the About page shows "running since" (#521)
- Link to the licenses page on the About page, keeping the selected device (#528)
- Toast after every network scan that names the newly discovered devices
- `PUT /api/devices/{id}/source` switches a device to Bluetooth, AUX or AirPlay
- Translated restore step and validation messages via stable `message_code` / `message_params` (all 10 locales, English fallback)
- Cypress suites for responsive layout (overlap, overflow and clipping audit) and for axe accessibility of every wizard state
- Machine-readable `code`, `params` and `extra` in API error responses (`ErrorDetail`), `errors[].path`/`code` for field errors, `raise_coded()` and an error-code registry (`core/error_codes.py`); all existing keys are unchanged.
- Frontend: typed `ApiError` thrown by `throwIfNotOk` and translated messages via `getApiErrorMessage`/`getFieldErrors` (`errors.api.*` in all locales).

### Changed
- Renaming a device uses only the device REST API (`POST /name`, like the Bose app). The SSH fallback that edited `SystemConfigurationDB.xml` was removed, a failed rename now answers 502 and leaves the stored name unchanged; control characters in the name are rejected (422)
- The navigation entry "Presets" is now "Devices" (all 10 locales). The device card is the single place for a device: now playing with a source switch (Presets, Bluetooth, AUX), previous/next/play keys for sources with tracks, volume, presets and remove
- Preset rows are toggles: a tap starts, pauses or resumes the preset; a small button next to it changes the station (behaviour change: the tap on the name used to open the station search). "Presets" in the source switch plays the preset the device played last
- The "Local control" page (`/local`) was removed; it was not linked anywhere and its source chips did not switch anything. Its functions live on the device card
- Restore: backup timeout raised to 10 minutes; archive validation searches the whole archive
- Device cards load from a small in-memory cache that is warmed for the neighbouring devices only
- Settings: a failed log download shows a translated reason instead of failing silently (#527)
- Frontend: the wire-shape interface `ApiError` is now `ApiErrorBody`.
- `ErrorDetail` and `ErrorItem` are part of the generated OpenAPI schema.
- `/health` has a typed response model (`HealthResponse`) in the OpenAPI schema; the frontend type is generated from it.
- The SoundTouch WebSocket client uses the `websockets.asyncio` API and ignores `HTTP(S)_PROXY`/`ALL_PROXY` for LAN devices; minimum `websockets` is now 15.0.

### Fixed
- Devices without the OCT redirect block in `/etc/hosts` were reported as `configured` by the health check and the setup verification (the grep fallback printed a second `0`)
- A second device scan now gets an explicit "already in progress" event instead of a bare HTTP 409, so real failures are no longer labelled "already running"
- Layout overflow and overlap on the presets, local control, multi-room and settings pages, the swiper, the navigation and the empty state
- False "unexpected content" warnings when validating a restore archive
- Accessibility: skip link and `main` landmark, heading order, contrast tokens, translated `aria-label`s, `html lang` sync, toast roles and reduced-motion support
- ci(pr-review): welcome comment no longer repeats for returning contributors; merged PRs are now counted per author, returning contributors get a shorter message and the label `contributor:trusted`

---

## [1.4.2] - 2026-05-29

### Added
- ci): show computed version in release workflow run title
- kb-growth): add Pattern & Quality Scan script and update workflow
- pr-review): upgrade to gpt-4o with enhanced review prompt
-  improve PR review quality based on production data
-  add AI-powered PR review automation via oct-support (#278
### Fixed
- ci): update trivy-action from deleted 0.28.0 to v0.36.0
-  propagate OCT_PORT to all device-facing URLs (#268) (#277
-  detect device config status via /info margeURL at startup (#267) (#281
- pr-review): filter legacy 'AI Review' job name from CI status checks
-  prevent issue-handler from hijacking PR comments and fix comment-trigger auth
-  PR review waits for CI completion before reviewing/approving
-  resolve actual LAN IP for wizard server-info (#200) (#276
-  validate diff line numbers for inline review comments
-  use base.ref instead of base.sha for PR review checkout
- i18n): translate missing wizard and restore keys for all locales (#265
- issue-handler): handle 410 Gone for deleted issues (#264
- issue-handler): handle 410 Gone for deleted issues
- i18n): shorten USB volume label to SOUNDTOUCH for FAT32 compatibility (#253
### Changed
-  rename AI Review job to PR Review
## [1.2.8] - 2026-05-16

### Added
- restore-wizard): implement full restore wizard (005
-  add post-release workflow for updating CHANGELOG and creating announcement discussions
### Fixed
- setup): prevent false-positive proxy detection in wizard (#184
-  optimize Dockerfile with caching for apt and pip installations
## [1.1.1] - 2026-04-12

### Fixed
- **Config file path detection (Issue #78)** — Auto-detect config at `/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml` or `/mnt/nv/OverrideSdkPrivateCfg.xml`; redirect writes to writable `/mnt/nv/` when original is on read-only filesystem
- **Vite 8 rolldown compatibility** — Fix `manualChunks` config (function instead of object)

---

## [1.1.0] - 2026-03-21

### Added
- **Multi-Room Zone Management** — Create, manage and dissolve speaker zones directly from the UI
- **Setup Status Badge** — Gear icon on device cards shows live setup state (unknown/configured/outdated/failed/offline), persisted in DB
- **Health-Check Background Task** — Periodic SSH verification to detect outdated or offline devices
- **Dual-Strategy Setup Wizard** — Wizard auto-detects whether an HTTPS reverse proxy is available on port 443 and adapts the configuration strategy (hosts-only vs. BMX + hosts)
- **Wizard Completion Endpoint** — `POST /api/setup/wizard/complete` persists `setup_status = configured` in DB when wizard finishes

### Changed
- **Volume Slider** — Replaced with DOM-direct RAF slider (A3) to eliminate drag lag; `onVolumeChange` fires only on pointer-up
- **Preset UX** — Overhauled with play button, overwrite confirmation dialog, and station logos
- **Setup Wizard** — Removed guided/manual mode selector; wizard starts directly in guided mode renamed to "Geführte Installation"
- **UX Polish** — Improved volume slider, delete button, cloud badge, info box
- Multi-room zone card layout improved; master device correctly shown in zone member list

### Fixed
- BUG-03: `/etc/hosts` entries now always use numeric IP (resolved via `socket.gethostbyname`); hostname like `hera` is no longer written to hosts file
- Zone master injection re-applied; master device perspective preferred in `get_all_zones`
- Device card drag disabled to prevent accidental swipe-navigation
- Zone card blue border removed
- Slider drag lag eliminated by removing inline styles during drag

---

## [1.0.0] - 2026-03-09

### Added
- **Setup Wizard** — Manual device configuration via SSH and USB stick
- **Raspberry Pi SD card images** — Pre-built images for Pi 3/4/5 (arm64 + armhf)
- **Multi-arch Docker images** — amd64, arm64, arm/v7
- **Upgrade guide** (UPGRADING.md) — Version-to-version migration documentation
- **Documentation** — Bilingual Wiki pages (DE/EN), API docs, Troubleshooting guide
- Docker Compose deployment template
- This changelog

### Changed
- Docker image now supports `stable` tag for production use
- Pinned all dependencies to exact versions

### Fixed
- CORS configuration now uses explicit default origins instead of wildcard
- SQLite index name collision between devices and presets tables
- XML namespace handling in SSDP discovery
- Database filename typo in config (ct.db → oct.db)
- Pi-gen build compatibility for both arm64 and armhf architectures

### Security
- Container vulnerability scanning enabled
- Automated dependency security updates

---

## [0.2.0] - 2026-02-01

### Added
- SSDP device discovery for automatic SoundTouch detection
- Preset management supporting slots 1-6
- RadioBrowser.info integration for internet radio search
- Manual device IP configuration for networks without multicast
- Device swiper navigation for browsing multiple devices
- Mock mode for local development without physical devices
- Health check endpoint for container monitoring
- Comprehensive test suite (348 backend + 260 frontend + 36 E2E tests)

### Changed
- Migrated from monolith to Clean Architecture
- React UI rewritten with modern hooks and TypeScript
- Switched from Flask to FastAPI for backend
- Replaced synchronous HTTP with async httpx
- Containerized deployment with Docker/Podman support

### Fixed
- Device synchronization race conditions
- Preset loading reliability
- WebSocket connection handling

---

## [0.1.0] - 2026-01-15

### Added
- Initial release
- Basic device listing via manual configuration
- Basic web interface for device control
- Docker deployment support

### Known Issues
- No automatic device discovery (manual IP configuration required)
- Limited error handling in device communication
- No preset management

---

## Version History Summary

| Version | Date | Description |
|---------|------|-------------|
| 1.0.0 | 2026-03-09 | Setup Wizard (manual), Multi-arch Docker, RasPi images |
| 0.2.0 | 2026-02-01 | Major release: SSDP discovery, presets, radio search |
| 0.1.0 | 2026-01-15 | Initial release: basic device control |

---

## Upgrade Notes

### Upgrading from 0.1.x to 0.2.x

**Database Migration:**
- Database schema changed (added presets table)
- Backup existing database: `cp /data/oct.db /data/oct.db.backup`
- Restart container - schema migrations run automatically

**Configuration Changes:**
- `config.yaml` format updated (see config.example.yaml)
- `CT_*` environment variables renamed to `OCT_*`
- CORS defaults changed from `["*"]` to explicit localhost origins

**API Breaking Changes:**
- `/api/devices/list` renamed to `/api/devices`
- Device ID field changed from `id` to `device_id`

---

## Release Process

Releases are fully automated via GitHub Actions:

1. Go to **Actions → Release → Run workflow**
2. Enter version number (e.g., `1.1.0`)
3. The workflow automatically:
   - Bumps version in all package files
   - Updates this CHANGELOG
   - Creates Git tag and GitHub Release
   - Builds and pushes Docker images (amd64, arm64, arm/v7)
   - Builds Raspberry Pi SD card images
   - Attaches all artifacts to the release

See [UPGRADING.md](UPGRADING.md) for version-specific migration guides.

---

**Maintained by:** OpenCloudTouch Contributors  
**License:** Apache License 2.0  
**Repository:** https://github.com/opencloudtouch/opencloudtouch
