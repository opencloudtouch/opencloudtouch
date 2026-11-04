# Configuration Reference

OpenCloudTouch is configured via `OCT_`-prefixed environment variables (case-insensitive), read by `AppConfig` in [`apps/backend/src/opencloudtouch/core/config.py`](../apps/backend/src/opencloudtouch/core/config.py). This page documents every variable; see [README.md](../README.md#configuration) for the short version.

## Server

| Variable | Default | Description |
|----------|---------|-------------|
| `OCT_HOST` | `0.0.0.0` | API bind address |
| `OCT_PORT` | `7777` | API port |
| `OCT_LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` \| `CRITICAL` |
| `OCT_LOG_FORMAT` | `text` | `text` or `json` |
| `OCT_LOG_FILE` | unset | Optional log file path |
| `OCT_LOG_DIR` | unset | Directory for persistent clustered log files (e.g. `/logs`); if set, each log cluster writes a `RotatingFileHandler` here |

## CORS

| Variable | Default | Description |
|----------|---------|-------------|
| `OCT_CORS_ORIGINS` | localhost dev ports + `OCT_PORT` | JSON array of allowed origins. Use `["*"]` for development only. The configured `OCT_PORT` is automatically appended if not already present. |

## Mock Mode & Database

| Variable | Default | Description |
|----------|---------|-------------|
| `OCT_MOCK_MODE` | `false` | Enable mock mode (no real devices required — useful for UI development) |
| `OCT_DB_PATH` | auto | SQLite database path. Empty = auto-configured: `:memory:` when `CI=true`, `data-local/oct-test.db` in mock mode, otherwise `/data/oct.db` |

## Discovery & Device Polling

| Variable | Default | Description |
|----------|---------|-------------|
| `OCT_DISCOVERY_ENABLED` | `true` | Enable SSDP/UPnP discovery |
| `OCT_DISCOVERY_TIMEOUT` | `3` | Discovery timeout (seconds) |
| `OCT_MANUAL_DEVICE_IPS` | `""` | Comma-separated fallback IPs, used when SSDP discovery doesn't find a device (e.g. different subnet, discovery disabled) |
| `OCT_DEVICE_POLLING_ENABLED` | `true` | Enable the periodic background alive-polling task (ping every 5 min, SSH BMX verify every 30 min, zone sync every 15 min). Disable if your devices are mostly offline and the polling noise/load is unwanted. |

## Device Ports & Station Descriptor

| Variable | Default | Description |
|----------|---------|-------------|
| `OCT_DEVICE_HTTP_PORT` | `8090` | SoundTouch device HTTP API port |
| `OCT_DEVICE_WS_PORT` | `8080` | SoundTouch device WebSocket port |
| `OCT_STATE_CACHE_MAX_AGE` | `10.0` | Max age (seconds) for WebSocket-fed state cache before falling back to an HTTP poll |
| `OCT_STATION_DESCRIPTOR_BASE_URL` | `http://localhost:7777` | Base URL OCT advertises to devices for preset programming. If left as `localhost`, it's automatically replaced with `content.api.bose.io:<port>` (devices resolve this via `/etc/hosts` redirect) since devices can't reach the server's own `localhost`. |

## Device settings (language, clock, power saving)

Three per-device settings can be read and written through the API (no `OCT_*` variable, the values live on the speaker):

| Endpoint | Purpose |
|----------|---------|
| `GET /api/devices/{id}/settings` | Display language, standby clock and power saving in one response, with `available.<name>` flags and the list of allowed `languages` |
| `PUT /api/devices/{id}/settings/language` | `{"language_id": 2}` — allow-listed ids only (1–25 except 14) |
| `PUT /api/devices/{id}/settings/clock` | `{"enabled": true, "time_format": "24h" \| "12h", "timezone": "Europe/Berlin"}`; with `enabled: false` only the clock is switched off and format/zone stay as they are |
| `PUT /api/devices/{id}/settings/power-saving` | `{"enabled": true}` |

- **Each setting is independent.** A speaker that does not support one of them (older models, soundbars) reports it as `null` with `available.<name> = false`; a write to such a setting returns `409 setting_not_available`. An unreachable speaker is `503 device_unreachable`; a speaker that answers a write with an HTTP error is `502 device_rejected`.
- **`applied` tells whether the speaker really kept the value.** After every write OCT reads the setting back and returns `{"applied": true|false, "value": …}` with what the speaker reports now. `applied: false` (HTTP 200) means the speaker accepted the request but did not keep the value — some models ignore unknown time zones or languages without a display font, or revert after a reboot. If the read-back fails, `applied` is `false` and `value` is `null`.
- **Persistence is not guaranteed.** Whether a setting written over HTTP survives a speaker reboot is unknown and may differ per model; OCT does not re-apply settings after a reboot.
- **Time zones** are IANA names (`Europe/Berlin`, `Asia/Tokyo`, `UTC`) checked against the `tzdata` package; POSIX strings such as `CET-1CEST` are rejected with `settings_timezone_invalid`.
- **Mock mode** (`OCT_MOCK_MODE=true`) keeps the three settings in memory per mock device.
- **Hardware note:** the endpoints (`/language`, `/clockDisplay`, `/systemtimeout`) and their XML come from a community patch for SoundTouch 10/20/30 and are **not verified against Bose documentation or other models**.

## Stream recovery

Internet-radio stations sometimes close the connection after a maximum listener time (often exactly 6 hours); the speaker then reports the source `INVALID_SOURCE` and goes idle. The opt-in **stream recovery** watchdog presses the matching preset key again. It is **off by default** because it makes a speaker play at an unexpected time (for example at night). No `OCT_*` variable; the settings are stored in the database.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/stream-recovery` | `{"enabled": false, "min_play_seconds": 600, "max_attempts_per_hour": 3, "updated_at": null}` |
| `PUT /api/stream-recovery` | Full replacement of the three fields; applied immediately |
| `GET /api/stream-recovery/events?limit=20` | Activity log, newest first (at most 100 are kept) |

- **Trigger (all must hold):** a speaker that played an internet-radio source (`LOCAL_INTERNET_RADIO` or `INTERNET_RADIO`) in `PLAY_STATE` or `BUFFERING_STATE` for at least `min_play_seconds` (60–86400, default 600) suddenly reports `INVALID_SOURCE`. A stop, pause or power-off never matches; a station that fails right away (shorter than `min_play_seconds`) never matches. TuneIn, Bluetooth, AUX, Spotify and DLNA are not handled.
- **Which preset:** the preset of that speaker whose station name equals the station that was playing (case and surrounding or repeated whitespace are ignored). If none matches, OCT logs `skipped_no_preset` and does nothing.
- **Limits:** a press is verified for 45 s (a `PLAY_STATE` on a radio source counts, `BUFFERING_STATE` does not). After a failed verification the next attempt starts after 60 s, as long as fewer than `max_attempts_per_hour` (1–10, default 3) presses were made in the last 60 minutes; then OCT records `gave_up`. A drop while the limit is used up records `skipped_rate_limited` without a press. The counters live in memory and reset on restart.
- **Stopping yourself wins:** if you stop, power off or start something else while a recovery is pending, the sequence ends silently.
- **Activity log:** outcomes `resumed`, `gave_up`, `skipped_no_preset`, `skipped_rate_limited`. `error_code` of a `gave_up` row is `device_unreachable`, `device_not_found` or `stream_recovery_failed` when the last key press failed; it holds no exception text, IP address or URL. `resumed` and `gave_up` are also logged at INFO.
- **Limitations:** the state manager merges `NOW_PLAYING` events within 500 ms (last wins), so an `INVALID_SOURCE` that is replaced inside that window is not seen. After more than 20 event subscribers the manager drops all subscriptions; the watchdog checks every 30 s, subscribes again and logs a WARNING, and events published in the gap are lost. A full event queue (200) also drops events.
- **Mock mode** has no WebSocket events, so nothing is ever pressed; the endpoints work.
- **What it does not do:** it does not reconnect inside the audio stream (for Orion presets the speaker opens the station itself), does not handle zones, and does not notify you.
- **Hardware assumptions (unverified):** a station-side close shows up as `INVALID_SOURCE`, and the event sequence before it is `PLAY_STATE` or `BUFFERING_STATE`; re-sending `PRESET_n` starts the preset on SoundTouch 10/20/30 (the Wave SoundTouch IV is reported not to); the speaker's station name equals the stored preset name.
- **Diagnostics:** the stream proxy now logs `[STREAM END] … elapsed=<seconds>` at INFO when a stream ends without OCT stopping it (upstream end or error, client disconnect).

## Bug Reports & Production Safety

| Variable | Default | Description |
|----------|---------|-------------|
| `OCT_GITHUB_TOKEN` | `""` | GitHub token used to create bug-report issues from the UI (optional) |
| `OCT_GITHUB_REPO` | `""` | `owner/repo` target for bug reports (optional) |
| `OCT_ALLOW_DANGEROUS_OPERATIONS` | `false` | Allow destructive endpoints such as `DELETE /api/devices` — testing only, do not enable in production |

## Docker Build Arguments

These are **build-time** (`docker build --build-arg ...`), not runtime environment variables — set once when the image is built, baked into the image afterward.

| Build Arg | Description |
|-----------|-------------|
| `OCT_BUILD_SIGNATURE` | HMAC-SHA256 signature of the version, produced only by CI. Marks a build as "official" (`is_official_build()`, exposed as `build: "official"` on `/health`). Cannot be produced locally — self-built images are always `"community"`. |
| `OCT_VERSION` | Optional override for the reported version string. Not required for a correct version — the real `pyproject.toml` version is already baked into every image via package metadata, official or self-built. Only useful for forks that want to stamp a custom version string. Example: `docker build --build-arg OCT_VERSION=my-fork-2.0.0 ...` |

See [`deployment/README.md`](../deployment/README.md#build-arguments) for build examples.

## Also See

- [Troubleshooting](TROUBLESHOOTING.md)
- [`.env` file structure](../ENV-FILES.md) — which `.env` file to use for local dev vs. deployment
