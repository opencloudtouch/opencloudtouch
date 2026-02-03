# CloudTouch Backend

FastAPI-basierter REST-API-Server für Bose SoundTouch Geräte.

## ✨ Features

- 🔍 **Device Discovery**: SSDP/UPnP + Manual IP Fallback
- 📡 **SoundTouch API Client**: Full device control (info, now_playing, volume, presets)
- 📻 **Radio Integration**: RadioBrowser API adapter
- 💾 **SQLite Storage**: Device inventory & settings persistence
- 🔐 **Production Guards**: Protected DELETE endpoints
- ⚡ **Clean Architecture**: Service layer, repository pattern, dependency injection

## 📊 Quality Metrics

- **Tests**: 268 passing (Unit + Integration + E2E)
- **Coverage**: 88% (Target: ≥80%) 🎯
- **Code Quality**: Ruff clean, 99% adapter coverage
- **Architecture**: Zero global state, SOLID principles

## Installation

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -e .[dev]
```

## Ausführen

### Development Mode

```bash
# Als Modul (empfohlen)
python -m cloudtouch

# Mit Uvicorn direkt
uvicorn cloudtouch.main:app --reload --host 0.0.0.0 --port 8000

# Mit Umgebungsvariablen
CT_LOG_LEVEL=DEBUG CT_DISCOVERY_TIMEOUT=15 python -m cloudtouch
```

### Production Mode

```bash
# Optimiert für Production
uvicorn cloudtouch.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 🧪 Tests

### Quick Tests

```bash
cd backend

# Alle Tests
pytest

# Mit Coverage
pytest --cov=cloudtouch --cov-report=html

# Nur Unit Tests
pytest tests/unit/

# Nur Integration Tests
pytest tests/integration/

# Spezifischer Test
pytest tests/unit/devices/test_adapter.py -v

# Mit Ausgabe
pytest -v -s
```

### Coverage Report

```bash
# HTML Report generieren
pytest --cov=cloudtouch --cov-report=html

# Report öffnen
start htmlcov/index.html  # Windows
open htmlcov/index.html   # macOS
xdg-open htmlcov/index.html  # Linux
```

### Test-Anforderungen

- Minimum 80% Coverage (aktuell: 88%)
- Alle Tests müssen grün sein vor Commit
- Pre-commit Hook läuft automatisch

## 📁 Struktur

```
backend/
├── src/cloudtouch/          # Hauptpaket (pip-installable)
│   ├── __init__.py
│   ├── main.py              # FastAPI Application Entry Point
│   ├── core/                # Shared Infrastructure
│   │   ├── config.py        # Pydantic Settings (ENV-based)
│   │   ├── logging.py       # Structured JSON Logging
│   │   └── exceptions.py    # Custom Exception Classes
│   ├── devices/             # Device Management Domain
│   │   ├── adapter.py       # SoundTouch Client Adapter (99% coverage)
│   │   ├── client.py        # HTTP Client Wrapper
│   │   ├── repository.py    # SQLite Device Repository
│   │   ├── capabilities.py  # Device Capability Detection
│   │   ├── api/
│   │   │   └── routes.py    # Device API Endpoints
│   │   ├── services/
│   │   │   └── sync_service.py  # Device Sync Service (Clean Architecture)
│   │   └── discovery/
│   │       ├── ssdp.py      # SSDP/UPnP Discovery
│   │       ├── manual.py    # Manual IP Fallback
│   │       └── mock.py      # Mock Discovery (Testing)
│   ├── radio/               # Radio Station Domain
│   │   ├── provider.py      # Abstract Radio Provider
│   │   ├── providers/
│   │   │   └── radiobrowser.py  # RadioBrowser API Implementation
│   │   └── api/
│   │       └── routes.py    # Radio API Endpoints
│   ├── settings/            # Settings Domain
│   │   ├── repository.py    # Settings Repository
│   │   └── routes.py        # Settings API Endpoints
│   └── db/                  # Database Layer
│       └── __init__.py      # SQLite Connection Management
├── tests/                   # Test Suite (268 tests)
│   ├── unit/                # Unit Tests (fast, isolated)
│   │   ├── core/            # Core module tests
│   │   ├── devices/         # Device domain tests
│   │   │   ├── test_adapter.py      # 20 tests, 99% coverage
│   │   │   ├── test_repository.py
│   │   │   ├── api/
│   │   │   └── discovery/
│   │   │       └── test_ssdp.py     # 18 tests, 73% coverage
│   │   └── radio/           # Radio domain tests
│   ├── integration/         # Integration Tests (API-level)
│   │   └── test_real_api_stack.py
│   └── real/                # Real Device Tests (optional)
│       └── test_discovery_real.py
├── pyproject.toml           # Python Packaging (PEP 517/518)
├── pytest.ini               # Pytest Configuration
├── requirements.txt         # Production Dependencies
├── requirements-dev.txt     # Development Dependencies
└── Dockerfile               # Backend Container Image
```

## 🔧 Konfiguration

### Umgebungsvariablen

Alle Konfigurationen nutzen das Präfix `CT_`:

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `CT_HOST` | `0.0.0.0` | API Bind-Adresse |
| `CT_PORT` | `8000` | API Port |
| `CT_LOG_LEVEL` | `INFO` | Log-Level (DEBUG, INFO, WARNING, ERROR) |
| `CT_DB_PATH` | `./data/ct.db` | SQLite Datenbankpfad |
| `CT_DISCOVERY_TIMEOUT` | `10` | SSDP Discovery Timeout (Sekunden) |
| `CT_MANUAL_DEVICE_IPS` | `[]` | Manuelle Geräte-IPs (komma-separiert) |

### Beispiel .env

```bash
CT_LOG_LEVEL=DEBUG
CT_DISCOVERY_TIMEOUT=15
CT_MANUAL_DEVICE_IPS=192.168.1.100,192.168.1.101
```

## 📡 API Endpoints

### Devices

- `GET /api/devices` - List all devices
- `POST /api/devices/sync` - Trigger device discovery & sync
- `GET /api/devices/{device_id}` - Get device details
- `GET /api/devices/{device_id}/capabilities` - Get device capabilities
- `DELETE /api/devices/{device_id}` - Delete device (production-guarded)

### Radio

- `GET /api/radio/search?type=name&query=rock&limit=10` - Search stations
- `GET /api/radio/station/{uuid}` - Get station details

### Settings

- `GET /api/settings/manual-ips` - Get manual IP configuration
- `POST /api/settings/manual-ips` - Update manual IPs (bulk)

### Health

- `GET /health` - Health check endpoint

## 🏗️ Architektur-Prinzipien

### Clean Architecture

```
API Layer (FastAPI Routes)
    ↓
Service Layer (Business Logic)
    ↓
Domain Models (Entities)
    ↓
Adapters (External Systems)
    ↓
Infrastructure (DB, Config)
```

**Regeln**:
- Abhängigkeiten fließen von außen nach innen
- Domain Layer kennt keine Infrastruktur
- Services orchestrieren Use Cases
- Repositories abstrahieren Datenzugriff

### SOLID Principles

- **Single Responsibility**: DeviceSyncService, DeviceRepository
- **Open/Closed**: Radio Provider abstraction für Extensions
- **Liskov Substitution**: Mock/Real Discovery austauschbar
- **Interface Segregation**: Kleine, fokussierte Interfaces
- **Dependency Inversion**: Injection via FastAPI Depends()

### Test-Driven Development (TDD)

Alle Änderungen folgen RED → GREEN → BLUE:
1. 🔴 **RED**: Test schreiben (schlägt fehl)
2. 🟢 **GREEN**: Code schreiben (Test besteht)
3. 🔵 **BLUE**: Refactoring (Test bleibt grün)

## 🐛 Troubleshooting

### Tests schlagen fehl

```bash
# Cache leeren
pytest --cache-clear

# Verbose Output
pytest -vv -s

# Nur einen Test
pytest tests/unit/devices/test_adapter.py::test_get_info_success -vv
```

### Import Errors

```bash
# Paket neu installieren
pip install -e .[dev]

# PYTHONPATH prüfen
echo $PYTHONPATH  # Linux/Mac
echo $env:PYTHONPATH  # Windows PowerShell
```

### Coverage zu niedrig

```bash
# Detaillierter Coverage Report
pytest --cov=cloudtouch --cov-report=term-missing

# Coverage für spezifisches Modul
pytest --cov=cloudtouch.devices.adapter --cov-report=term-missing
```

## 🤝 Contributing

Siehe [../CONTRIBUTING.md](../CONTRIBUTING.md) für:
- Code Style Guidelines (PEP 8, Naming Conventions)
- Commit Message Format (Conventional Commits)
- Pull Request Process

## 📄 Lizenz

Apache License 2.0 - Siehe [../LICENSE](../LICENSE)
