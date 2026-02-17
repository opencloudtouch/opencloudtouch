# OpenCloudTouch (OCT)

**OpenCloudTouch** ist eine lokale Open-Source-Loesung fuer **Bose®-Geräte der SoundTouch®-Serie** nach dem Cloud-Ende.

Ziel: SoundTouch®-Lautsprecher (z. B. SoundTouch® 10/30/300) weiter nutzen, ohne Bose®-Cloud und ohne proprietaere App.

> Leitidee: Ein Container, eine Web-App, lokale Steuerung.

**Trademark Notice**: OpenCloudTouch (OCT) is not affiliated with Bose® Corporation. Bose® and SoundTouch® are registered trademarks of Bose® Corporation. See `TRADEMARK.md`.

## Features

- Internetradio und Presets (1-6)
- Web-UI fuer Desktop und Smartphone
- Device Discovery via SSDP/UPnP + manuelle IP-Fallbacks
- Preset-Programmierung inkl. lokaler Descriptor-/Playlist-Endpunkte
- Setup-Wizard fuer Geraetekonfiguration
- BMX-kompatible Endpunkte fuer SoundTouch® (inkl. TuneIn-Resolver-Route)
- Docker-Deployment (amd64 + arm64)

## Architektur (Kurzfassung)

```text
Browser UI
   ->
OpenCloudTouch (FastAPI + React, im Container)
   ->
SoundTouch® Geraete im lokalen Netzwerk (HTTP/WebSocket)
```

Radio-Provider sind per Adapter abstrahiert. Aktuell ist RadioBrowser integriert.

## Installation & Quickstart

### Option 1: Docker Compose (empfohlen)

1. Repository klonen:

```bash
git clone https://github.com/scheilch/opencloudtouch.git
cd opencloudtouch
```

2. Container starten:

```bash
docker compose -f deployment/docker-compose.yml up -d --build
```

3. Web-UI oeffnen:

```text
http://localhost:7777
```

4. Logs:

```bash
docker compose -f deployment/docker-compose.yml logs -f
```

5. Stoppen:

```bash
docker compose -f deployment/docker-compose.yml down
```

### Option 2: Docker Run (GHCR Image)

```bash
docker run -d \
  --name opencloudtouch \
  --network host \
  -v oct-data:/data \
  ghcr.io/scheilch/opencloudtouch:latest
```

Beispiel fuer einen commit-spezifischen Tag:

```bash
docker pull ghcr.io/scheilch/opencloudtouch:main-6ce3982
```

## Projekt-Struktur

```text
opencloudtouch/
|- apps/
|  |- backend/
|  |  |- src/opencloudtouch/        # FastAPI Backend
|  |  |- tests/                     # Unit/Integration/E2E/Real Tests
|  |  |- pyproject.toml
|  |  |- requirements.txt
|  |  `- requirements-dev.txt
|  `- frontend/
|     |- src/                       # React + TypeScript
|     |- tests/
|     `- package.json
|- deployment/
|  |- docker-compose.yml
|  `- local/                        # PowerShell Deploy/Utility Scripts
|- docs/
|- scripts/
|  |- e2e-runner.mjs
|  |- install-hooks.ps1
|  `- install-hooks.sh
|- Dockerfile
|- package.json
`- README.md
```

## Lokale Entwicklung

### Voraussetzungen

- Node.js >= 20
- npm >= 10
- Python >= 3.11

### Quick Start (Root)

```bash
# Node dependencies
npm install

# Python venv + backend deps
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -e apps/backend
pip install -r apps/backend/requirements-dev.txt

# Backend + Frontend parallel starten
npm run dev
```

- Backend: `http://localhost:7777`
- Frontend (Vite dev): `http://localhost:5175`

### Backend manuell starten

```bash
python -m opencloudtouch
```

Alternative mit Uvicorn:

```bash
uvicorn opencloudtouch.main:app --reload --host 0.0.0.0 --port 7777
```

## Tests

### Empfohlen (Root)

```bash
npm test
npm run test:backend
npm run test:frontend
npm run test:e2e
npm run lint
```

### Direkt in den Workspaces

```bash
# Backend
cd apps/backend
pytest -v --cov=opencloudtouch --cov-report=html
pytest tests/unit/radio/providers/test_radiobrowser.py -v

# Frontend
cd apps/frontend
npm test
npm run test:coverage
npm run test:e2e:open
```

## Troubleshooting

### Container startet nicht

```bash
docker compose -f deployment/docker-compose.yml logs opencloudtouch
```

### Health-Check im Container testen

```bash
docker exec opencloudtouch python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:7777/health').status)"
```

### Geraete werden nicht gefunden

- `network_mode: host` verwenden (in `deployment/docker-compose.yml` bereits gesetzt)
- Geraete und OCT muessen im selben Netzwerk sein
- Fallback ueber `OCT_MANUAL_DEVICE_IPS` nutzen

### Port 7777 ist belegt

```bash
OCT_PORT=8080 docker compose -f deployment/docker-compose.yml up -d
```

## Konfiguration

Aktuell erfolgt die Konfiguration primär ueber `OCT_`-Umgebungsvariablen.

- Beispielwerte: `.env.template`
- Vollstaendige Referenz: `config.example.yaml` und `docs/CONFIGURATION.md`

Wichtige Variablen:

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `OCT_HOST` | `0.0.0.0` | API Bind-Adresse |
| `OCT_PORT` | `7777` | API Port |
| `OCT_LOG_LEVEL` | `INFO` | Log-Level |
| `OCT_DB_PATH` | `/data/oct.db` | SQLite-Pfad (Produktivbetrieb) |
| `OCT_DISCOVERY_ENABLED` | `true` | Discovery aktivieren |
| `OCT_DISCOVERY_TIMEOUT` | `5` | Discovery-Timeout in Sekunden |
| `OCT_MANUAL_DEVICE_IPS` | `""` | Komma-separierte manuelle IPs |

## Aktueller Stand

Bereits umgesetzt (Codebasis):

- Discovery/Sync fuer Geraete (`/api/devices/discover`, `/api/devices/sync`)
- RadioBrowser-Suche (`/api/radio/search`)
- Preset-Verwaltung (`/api/presets/...`) inkl. Station-Descriptor/Playlist-Routen
- Key-Press Endpoint fuer Preset-Tests (`/api/devices/{device_id}/key`)
- Setup-Wizard API (`/api/setup/...`)
- BMX-Routen fuer SoundTouch®-Kompatibilitaet (inkl. TuneIn-Playback-Route)
- Frontend-Seiten fuer Radio, Presets, Multiroom, Firmware, Settings

Offen bzw. in Planung:

- Spotify-Integration (OAuth/Token-Handling)
- weitere Provider (Apple Music, Deezer, Music Assistant)
- rechtliche/ToS-Klaerung je Provider

## Mitmachen

Beitraege sind willkommen. Siehe `CONTRIBUTING.md`.

## Lizenz

Apache License 2.0. Siehe `LICENSE` und `NOTICE`.
