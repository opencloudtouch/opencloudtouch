# OpenCloudTouch (OCT)

> ## ⚠️ DISCLAIMER — USE AT YOUR OWN RISK / NUTZUNG AUF EIGENE GEFAHR
>
> This software modifies your Bose® SoundTouch® device configuration. **The authors accept no liability whatsoever for any damage, malfunction, or permanent failure ("bricking") of your devices.** Use is entirely at your own risk. See **[DISCLAIMER.md](DISCLAIMER.md)** for full terms in English and German.
>
> Diese Software verändert die Konfiguration Ihrer Bose® SoundTouch®-Geräte. **Die Autoren übernehmen keinerlei Haftung für Schäden, Fehlfunktionen oder dauerhaftes Versagen („Bricking") Ihrer Geräte.** Die Nutzung erfolgt ausschließlich auf eigene Gefahr. Vollständige Bedingungen in Deutsch und Englisch: **[DISCLAIMER.md](DISCLAIMER.md)**

**OpenCloudTouch** is a local, open-source solution for **Bose® SoundTouch® speakers** after the official cloud shutdown.

Keep your SoundTouch® speakers (e.g. SoundTouch® 10/30/300) running — without the Bose® cloud, without the proprietary app. One container, one web app, full local control.

> **Trademark Notice:** OpenCloudTouch is not affiliated with Bose® Corporation. Bose® and SoundTouch® are registered trademarks of Bose® Corporation. See [NOTICE](NOTICE).

| | |
|---|---|
| **Documentation** | [GitHub Wiki](https://github.com/opencloudtouch/opencloudtouch/wiki) (Deutsch / English) |
| **Discussions** | [GitHub Discussions](https://github.com/opencloudtouch/opencloudtouch/discussions) |
| **Releases** | [GitHub Releases](https://github.com/opencloudtouch/opencloudtouch/releases) |

## Features

- Internet radio with preset support (1–6 hardware buttons)
- Responsive web UI for desktop and mobile
- Device discovery via SSDP/UPnP + manual IP fallbacks
- Preset programming with local descriptor and playlist endpoints
- Setup wizard for manual device configuration (SSH/USB)
- Multi-room zone management
- BMX-compatible endpoints for SoundTouch® (including TuneIn stream resolver)
- Docker deployment on three architectures (amd64, arm64, arm/v7)
- Pre-built Raspberry Pi SD card images

## Architecture

```text
Browser UI
   →
OpenCloudTouch (FastAPI + React, single container)
   →
SoundTouch® devices on the local network (HTTP / WebSocket)
```

Radio providers are abstracted via adapters. RadioBrowser is the built-in search provider; TuneIn is supported as a stream resolver for existing device presets.

## Quick Start

### Option 1 — Docker Run (recommended)

```bash
docker run -d \
  --name opencloudtouch \
  --network host \
  -v opencloudtouch-data:/data \
  -e OCT_DISCOVERY_ENABLED=true \
  ghcr.io/opencloudtouch/opencloudtouch:latest
```

Open **http://localhost:7777** in your browser.

### Option 2 — Docker Compose

```bash
docker run -d \
  --name opencloudtouch \
  --network host \
  -v opencloudtouch-data:/data \
  -e OCT_DISCOVERY_ENABLED=true \
  ghcr.io/opencloudtouch/opencloudtouch:latest
```

Or use the provided compose file (pull mode, no build required):

```bash
docker compose -f deployment/docker-compose.yml pull
docker compose -f deployment/docker-compose.yml up -d
```

```bash
# View logs
docker compose -f deployment/docker-compose.yml logs -f

# Stop
docker compose -f deployment/docker-compose.yml down
```

> **Building from source?** The Dockerfile expects a pre-built frontend in `.out/dist/`.
> Run `cd apps/frontend && npm install && npm run build` first, then
> `docker compose -f deployment/docker-compose.yml up -d --build`.

### Option 3 — Raspberry Pi (SD Card Image)

Pre-built images for Raspberry Pi 3/4/5 are available on the [Releases page](https://github.com/opencloudtouch/opencloudtouch/releases).

1. Download the `.img.xz` for your board
2. Flash with [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
3. Boot — OpenCloudTouch starts automatically on port 7777
4. Default login: `oct` / `opencloudtouch`

### Docker Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest release (recommended) |
| `1.2.5` | Specific version |


### Supported Architectures

| Arch | Platform | Devices |
|------|----------|---------|
| `amd64` | x86_64 | Desktop, server, NAS |
| `arm64` | aarch64 | Raspberry Pi 4/5, Apple Silicon |
| `arm/v7` | armhf | Raspberry Pi 2/3 |

### Video Walkthrough

New to OpenCloudTouch? Watch this step-by-step setup tutorial:

[![OpenCloudTouch Setup Tutorial](https://img.youtube.com/vi/sGB9peEGNwQ/maxresdefault.jpg)](https://www.youtube.com/watch?v=sGB9peEGNwQ)

*by [Hoerli](https://www.youtube.com/@hoerli)*

## Project Structure

```text
opencloudtouch/
├── apps/
│   ├── backend/                  # FastAPI REST API (Python 3.11+)
│   │   ├── src/opencloudtouch/
│   │   └── tests/
│   └── frontend/                 # React + TypeScript (Vite 8)
│       ├── src/
│       └── tests/
├── deployment/
│   ├── Dockerfile                # Multi-stage production build
│   ├── docker-compose.yml
│   └── raspi-image/              # Raspberry Pi SD card build
├── scripts/                      # Git hooks, E2E runner
└── package.json                  # Monorepo root (npm workspaces)
```

## Local Development

### Prerequisites

- Node.js >= 20, npm >= 10
- Python >= 3.11

### Setup

```bash
# Install Node dependencies
npm install

# Create Python venv and install backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -e apps/backend
pip install -r apps/backend/requirements-dev.txt

# Start backend + frontend in parallel
npm run dev
```

- Backend: http://localhost:7777
- Frontend dev server: http://localhost:5175

### Running Tests

```bash
npm test                # All tests (backend + frontend + E2E)
npm run test:backend    # Backend unit tests with coverage
npm run test:frontend   # Frontend unit tests
npm run test:e2e        # Cypress E2E tests
npm run lint            # Linting (Ruff + ESLint)
```

## Configuration

Configuration uses `OCT_` environment variables. See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for the full reference.

| Variable | Default | Description |
|----------|---------|-------------|
| `OCT_HOST` | `0.0.0.0` | API bind address |
| `OCT_PORT` | `7777` | API port |
| `OCT_LOG_LEVEL` | `INFO` | Log level |
| `OCT_DB_PATH` | `/data/oct.db` | SQLite database path |
| `OCT_DISCOVERY_ENABLED` | `true` | Enable SSDP discovery |
| `OCT_DISCOVERY_TIMEOUT` | `5` | Discovery timeout (seconds) |
| `OCT_MANUAL_DEVICE_IPS` | `""` | Comma-separated fallback IPs |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Container won't start | `docker compose -f deployment/docker-compose.yml logs opencloudtouch` |
| Devices not found | Ensure `network_mode: host` and same network; use `OCT_MANUAL_DEVICE_IPS` as fallback |
| Port 7777 in use | `OCT_PORT=8080 docker compose -f deployment/docker-compose.yml up -d` |
| Health check | `docker exec opencloudtouch python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:7777/health').status)"` |

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more details.

## Roadmap

- Spotify integration (OAuth / token handling)
- Additional providers (Apple Music, Deezer, Music Assistant)

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for guidelines.

- [Conventional Commits](docs/CONVENTIONAL_COMMITS.md) are required
- Minimum 80% test coverage
- Pre-commit hooks enforce formatting and linting

## Community

Join the conversation in [GitHub Discussions](https://github.com/opencloudtouch/opencloudtouch/discussions) — ask questions, share your setup, or suggest features.

## License

[Apache License 2.0](LICENSE) — see [NOTICE](NOTICE) for trademark details.
