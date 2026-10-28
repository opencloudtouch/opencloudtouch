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
