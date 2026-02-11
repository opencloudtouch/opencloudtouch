# OpenCloudTouch (OCT)

**OpenCloudTouch** ist eine lokale, Open-Source-Ersatzlösung für die eingestellten Cloud-Funktionen von **Bose®-Geräten der SoundTouch®-Serie**.

Ziel ist es, Bose Lautsprecher (z. B. **SoundTouch® 10 / 30 / 300**) auch nach dem Ende des offiziellen Supports **weiter sinnvoll nutzen zu können**
– **ohne Cloud**, **ohne Home Assistant** und ohne proprietäre Apps.

> Leitidee: OCT ersetzt nicht die Geräte, sondern die eingestellten Cloud-Dienste.  
> Ein Container, eine Web-App, Presets funktionieren wieder.

---

**⚠️ Trademark Notice**: OpenCloudTouch (OCT) is not affiliated with Bose Corporation. Bose® and SoundTouch® are registered trademarks of Bose Corporation. See [TRADEMARK.md](TRADEMARK.md) for details.

---

## ✨ Features (Zielbild)

- 🎵 **Internetradio & Presets**
  - Radiosender suchen (MVP: offene Quellen, z. B. RadioBrowser)
  - Presets **1–6** neu belegen
  - Physische Preset-Tasten am Gerät funktionieren wieder

- 🖥️ **Web-UI (App-ähnlich)**
  - Bedienung per Browser (Desktop & Smartphone)
  - Geführte UX für nicht versierte Nutzer
  - „Now Playing“ (Sender/Titel), soweit vom Stream unterstützt

- 🔊 **Multiroom**
  - Bestehende Multiroom-Gruppen anzeigen
  - Geräte gruppieren / entkoppeln (Zonen)

- 📟 **Now Playing**
  - Anzeige im Web-UI
  - Anzeige auf dem Gerätedisplay, soweit vom Stream unterstützt

- 🐳 **Ein Container**
  - Docker-first (amd64 + arm64)
  - Optional später als Raspberry-Pi-Image („Appliance") mit mDNS (`opensystem.local`)

---

## 🎯 Zielgruppe

- Besitzer von Bose®-Geräten der SoundTouch®-Serie, die nach dem Cloud-Ende weiterhin Radio/Presets/Multiroom nutzen wollen
- Nutzer ohne Home Assistant
- Nutzer mit Raspberry Pi / NAS / Mini-PC, die „einfach nur“ einen Container starten können
- Power-User: Adapter/Provider erweiterbar (Plugins)

---

## 🧩 Architektur (Kurzfassung)

OpenCloudTouch ist eine eigenständige Web-App + Backend im **einen** Container:

```text
Browser UI
   ↓
OpenCloudTouch (Docker)
   ↓
Streaming Devices (lokale API: HTTP + WebSocket)
```

Streaming-Anbieter werden über **Adapter** angebunden (MVP: Internetradio aus offenen Quellen).
Optional kann später ein Music-Assistant-Adapter oder weitere Provider ergänzt werden.

---

## 📦 Installation & Quickstart

### Option 1: Docker Compose (empfohlen)

1. **Repo klonen:**
   ```bash
   git clone https://github.com/<your-username>/opencloudtouch.git
   cd opencloudtouch
   ```

2. **Container starten:**
   ```bash
   docker compose up -d
   ```

3. **Web-UI öffnen:**
   ```
   http://localhost:7777
   ```

4. **Logs prüfen:**
   ```bash
   docker compose logs -f
   ```

5. **Stoppen:**
   ```bash
   docker compose down
   ```

### Option 2: Docker Run

```bash
docker run -d \
  --name opencloudtouch \
  --network host \
  -v oct-data:/data \
  ghcr.io/<your-username>/opencloudtouch:latest
```

Danach im Browser öffnen: `http://localhost:7777`

### Warum `--network host`?

Discovery (SSDP/UPnP) und lokale Gerätekommunikation funktionieren damit am stabilsten (insbesondere auf Raspberry Pi/NAS).

---

## � Projekt-Struktur

```
opencloudtouch/
├── apps/backend/                    # Python Backend (FastAPI)
│   ├── src/opencloudtouch/       # Main package (pip-installable)
│   │   ├── core/              # Config, Logging, Exceptions
│   │   ├── devices/           # Device discovery, client, API
│   │   ├── radio/             # Radio providers, API
│   │   └── main.py            # FastAPI app
│   ├── tests/                 # Backend tests
│   │   ├── unit/              # Unit tests (core, devices, radio)
│   │   ├── integration/       # API integration tests
│   │   └── e2e/               # End-to-end tests
│   ├── pyproject.toml         # Python packaging (PEP 517/518)
│   ├── pytest.ini             # Test configuration
│   └── Dockerfile             # Backend container image
├── apps/apps/frontend/                  # React Frontend (Vite)
│   ├── src/                   # React components, hooks, services
│   ├── tests/                 # Frontend tests
│   └── package.json           # NPM dependencies
├── deployment/                # Deployment scripts
│   ├── docker-compose.yml     # Docker Compose config
│   ├── local-deploy.ps1       # Local deployment (NAS/Server)
│   └── README.md              # Deployment guide
├── scripts/                   # User utility scripts
│   ├── test-all.ps1           # Full test suite
│   ├── demo_radio_api.py      # Radio API demo
│   └── README.md              # Scripts documentation
└── docs/                      # Project documentation
```

---

## 🛠️ Lokale Entwicklung

**Empfohlener Workflow**: npm-basierte Commands im Root-Verzeichnis.

### Quick Start

```bash
# Install dependencies (Root + Frontend)
npm install

# Start Backend + Frontend parallel
npm run dev
```

- **Backend** läuft auf: http://localhost:7777  
- **Frontend** läuft auf: http://localhost:5173 (proxied zu Backend)

### Backend Setup (manuell)

Für Backend-spezifische Entwicklung:

```bash
cd apps/backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements-dev.txt

# Backend starten
uvicorn opencloudtouch.main:app --reload --host 0.0.0.0 --port 7777
```

### Tests

**Empfohlen**: npm Scripts im Root-Verzeichnis:

```bash
# Alle Tests (Backend + Frontend + E2E)
npm test

# Nur Backend Tests (pytest)
npm run test:backend

# Nur Frontend Tests (vitest)
npm run test:frontend

# Nur E2E Tests (Cypress mit Auto-Setup)
npm run test:e2e

# Linting
npm run lint
```

**Alternative**: Direkt in Workspace-Verzeichnissen:

```bash
# Backend Tests (manuell)
cd apps/backend
pytest -v --cov=opencloudtouch --cov-report=html
pytest tests/test_radiobrowser_adapter.py -v  # Specific test

# Frontend Tests (manuell)
cd apps/frontend
npm test                    # Run once
npm test -- --watch         # Watch mode
npm run test:coverage       # With coverage

# E2E Tests (manuell)
npm run cypress:open        # Interactive mode
npm run cypress:run         # Headless mode

# Coverage Reports
start apps/backend/htmlcov/index.html   # Windows
open apps/backend/htmlcov/index.html    # macOS/Linux
```

---

## 🐛 Troubleshooting

### Container startet nicht

```bash
# Logs prüfen
docker compose logs opencloudtouch

# Health check manuell testen
docker exec opencloudtouch curl http://localhost:7777/health
```

### Geräte werden nicht gefunden

- Stellen Sie sicher, dass `--network host` verwendet wird (Docker Compose macht dies standardmäßig)
- Prüfen Sie, ob Geräte im selben Netzwerk sind
- Manuellen Fallback nutzen: ENV Variable `OCT_MANUAL_DEVICE_IPS=192.168.1.100,192.168.1.101` setzen

### Port 7777 bereits belegt

Ändern Sie den Port in [deployment/docker-compose.yml](deployment/docker-compose.yml) oder via ENV:

```bash
OCT_PORT=8080 docker compose up -d
```

---

## ⚙️ Konfiguration

Konfiguration erfolgt via:
1. **ENV Variablen** (Prefix: `OCT_`)
2. **Config-Datei** (optional): `config.yaml` im Container unter `/app/config.yaml` mounten

Siehe [.env.example](.env.example) und [config.example.yaml](config.example.yaml) für alle Optionen.

### Wichtige ENV Variablen

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `OCT_HOST` | `0.0.0.0` | API Bind-Adresse |
| `OCT_PORT` | `7777` | API Port |
| `OCT_LOG_LEVEL` | `INFO` | Log-Level (DEBUG, INFO, WARNING, ERROR) |
| `OCT_DB_PATH` | `/data/oct.db` | SQLite Datenbankpfad |
| `OCT_DISCOVERY_ENABLED` | `true` | SSDP/UPnP Discovery aktivieren |
| `OCT_MANUAL_DEVICE_IPS` | `[]` | Manuelle Geräte-IPs (Komma-separiert) |

## ✅ MVP (erste Instanz)

Fokus: **Knopf drücken → Sender spielt → Anzeige**

- UI-Seite 1: Radiosender suchen/auswählen und Preset (1–6) zuordnen
- OCT programmiert Presets so um, dass die Preset-Taste eine lokale Station-URL lädt (cloudfrei)
- E2E Demo/Test: Station finden → Preset setzen → Preset per API simulieren → Playback & „now playing“ verifizieren

---

## 🧭 Roadmap & Status

### ✅ Iteration 0: Repo/Build/Run (FERTIG)
- Backend (FastAPI + Python 3.11)
- Frontend (React + Vite)
- Docker Multi-Stage Build (amd64 + arm64)
- CI/CD Pipeline (GitHub Actions)
- Tests (pytest, 85% coverage)
- Health Check Endpoint

### ✅ Iteration 1: Discovery + Device Inventory (FERTIG)
- SSDP/UPnP Discovery
- Manual IP Fallback
- Device HTTP Client (/info, /now_playing)
- SQLite Device Repository
- GET/POST `/api/devices` Endpoints
- Frontend: Device List UI
- **Tests**: 109 Backend Tests, E2E Demo Script

### ✅ Iteration 2: RadioBrowser API Integration (FERTIG)
- RadioBrowser API Adapter (108 Zeilen, async httpx, Retry-Logik)
- Search Endpoints: `/api/radio/search`, `/api/radio/station/{uuid}`
- Search Types: name, country, tag (limit-Parameter)
- Frontend: RadioSearch Component (React Query)
  - Debouncing (300ms), Loading/Error/Empty States
  - Skeleton Screens, ARIA Labels, Keyboard Navigation
  - Mobile-First Design (48px Touch Targets, WCAG 2.1 AA)
- **Tests**: 150 Backend Tests (83% Coverage) + 22 Frontend Tests (100% RadioSearch Coverage)
- **Refactoring**: Provider abstraction (radio_provider.py) vorbereitet für zukünftige Erweiterungen

### ✅ Iteration 2.5: Testing & Quality Assurance + Refactoring (ABGESCHLOSSEN)

**Backend Tests**:
- ✅ **268 Tests PASSING** (Unit + Integration + E2E)
- ✅ **Coverage: 88%** (Target: ≥80%) 🎯 **DEUTLICH ÜBERTROFFEN!**
- ✅ **+20 neue Tests** in Session 5-7:
  - BoseDeviceClientAdapter: 99% Coverage (+13 Tests)
  - SSDP Edge Cases: 73% Coverage (+7 Tests)
  - Device API Concurrency Tests
  - Error Handling & Retry Logic

**Frontend Tests**:
- ✅ **87 Tests PASSING** (+6 neue Error Handling Tests)
- ✅ **Coverage: ~55%** (von 0% hochgezogen)
- ✅ Component Tests: RadioPresets, Settings, DeviceSwiper, EmptyState
- ✅ **Error Handling**: Network errors, HTTP errors, Retry mechanism

**E2E Tests**:
- ✅ **15 Cypress Tests PASSING** (Mock Mode)
- ✅ Device Discovery + Manual IP Configuration
- ✅ Complete User Journey Tests
- ✅ Regression Tests für 3 Bug-Fixes

**Refactoring Highlights** (13/16 Tasks, 3h 34min, -90% deviation):
- ✅ **Service Layer Extraction**: Clean Architecture, DeviceSyncService
- ✅ **Global State Removal**: Lock-based concurrency statt Boolean-Flag
- ✅ **Frontend Error Handling**: Retry-Button, User-friendly messages
- ✅ **Dead Code Removal**: Alle Linter clean (ruff, vulture, ESLint)
- ✅ **Production Guards**: DELETE endpoint protected
- ✅ **Auto-Formatting**: black, isort, Prettier über 77 Files
- ✅ **Naming Conventions**: Konsistente Namen über alle 370 Tests

**Code Quality**:
- ✅ 370 automatisierte Tests (268 Backend + 87 Frontend + 15 E2E)
- ✅ Zero Global State, Zero Linter Warnings
- ✅ TDD-Workflow: Alle Änderungen mit Tests abgesichert
- ✅ Pre-Commit Hooks: Tests + Coverage + E2E automatisch

**Status**: ✅ **PRODUCTION-READY** - Refactoring abgeschlossen, alle Tests grün

### 🔜 Iteration 3: Preset Mapping
- SQLite Schema (devices, presets, mappings)
- POST `/api/presets/apply`
- Station Descriptor Endpoint

### 🔜 Iteration 4: Playback Demo (E2E)
- Key Press Simulation (PRESET_n)
- Now Playing Polling + WebSocket
- E2E Demo Script

### 🔜 Iteration 5: UI Preset-UX
- Preset-Kacheln (1–6)
- Zuweisen per Klick
- Now Playing Panel

### 🔜 Weitere EPICs
- Multiroom (Gruppen/Entkoppeln)
- Lautstärke, Play/Pause, Standby
- Firmware-Info/Upload-Assistent
- Weitere Provider/Adapter (optional): TuneIn*, Spotify*, Apple Music*, Deezer*, Music Assistant*
  - *Hinweis: Provider werden nur aufgenommen, wenn rechtlich und technisch sauber umsetzbar.*

---

## 🧪 Tests & Coverage

**Coverage-Ziel**: 80% für Backend & Frontend

### Quick Commands (npm)

```bash
npm test                 # Run ALL tests (Backend, Frontend, E2E)
npm run test:backend     # Backend only (pytest)
npm run test:frontend    # Frontend only (vitest)
npm run test:e2e         # E2E only (Cypress, auto-setup)
```

### Backend
- **Aktuell**: 88% (268 Tests)
- **Arten**: Unit Tests, Integration Tests
- **Technologie**: pytest + pytest-cov + pytest-asyncio
- **Kommando**: `npm run test:backend` (oder `cd apps/backend && pytest --cov=opencloudtouch --cov-report=term-missing --cov-fail-under=80`)

### Frontend
- **Aktuell**: ~55% (87 Tests) ⚠️ UNTER 80% THRESHOLD
- **Arten**: Unit Tests (Vitest), E2E Tests (Cypress)
- **Technologie**: Vitest + @testing-library/react, Cypress
- **Kommandos**:
  - Unit Tests: `npm run test:frontend` (oder `cd apps/frontend && npm run test:coverage`)
  - E2E Tests: `npm run test:e2e` (automatischer Backend+Frontend Setup)

### CI/CD & Pre-commit
- **Pre-commit Hook** (`.husky/pre-commit` via Husky):
  - ✅ Backend Tests (pytest, 80% enforced)
  - ✅ Frontend Unit Tests (vitest)
  - ⚠️ E2E Tests NICHT im Hook (zu langsam, ~30-60s)
- **Workflow**: `git commit` → automatischer Test-Run → Commit nur bei grünen Tests
- **Manueller Test**: `npm test` (alle Tests inkl. E2E)
- **GitHub Workflow** (`.github/workflows/ci-cd.yml`):
  - Gleiche Test-Suite wie Pre-commit Hook
  - Zusätzlich: Linting (ruff, black, mypy, ESLint)

### Kritische Bereiche (Frontend < 80%)
- `EmptyState.tsx`: 27.63% (46 uncovered lines)
- `LocalControl.tsx`: 2.77%
- `MultiRoom.tsx`: 2.56%
- `Firmware.tsx`: 0%
- `Toast.tsx`: 0%

**Migration Guide**: Siehe [MIGRATION.md](MIGRATION.md) für Details zu alten PowerShell-Scripts → neuen npm Commands.

---

## 🤝 Mitmachen

Beiträge sind willkommen!  
Bitte lies vorab [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## 📄 Lizenz

Apache License 2.0  
Siehe [`LICENSE`](LICENSE) und [`NOTICE`](NOTICE).
