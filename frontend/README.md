# CloudTouch Frontend

Modern React SPA für die lokale Steuerung von Bose SoundTouch Geräten.

## Features

- **Swipeable Device Cards**: Intuitive Geräteauswahl mit Wischgesten
- **Empty State**: Benutzerführung beim ersten App-Start
- **Radio Presets**: Radiosender auf Preset-Tasten (1-6) verwalten
- **Local Control**: Lautstärke, Quellen, Playback-Steuerung
- **MultiRoom**: Zonen-Management für synchrone Wiedergabe
- **Firmware**: Geräte-Informationen und Firmware-Status
- **Settings**: Gerätekonfiguration und Discovery-Einstellungen
- **Licenses**: Open-Source Lizenzen aller verwendeten Bibliotheken

## Tech Stack

- **React** 18.2.0 - UI Framework
- **React Router** 6.20.0 - Client-side Routing
- **Framer Motion** 10.16.16 - Animations
- **Vite** 5.0.8 - Build Tool & Dev Server
- **Vitest** 1.0.4 - Testing Framework
- **Testing Library** - Component Testing
- **Cypress** 13.6.2 - E2E Testing (15 tests)

## Quality Metrics

- **Tests**: 87 unit/component tests (~55% coverage)
- **E2E Tests**: 15 Cypress integration tests
- **Code Quality**: ESLint clean, zero warnings
- **Architecture**: Service layer extracted, no global state

## Development

### Quick Start

```bash
# Install dependencies
npm install

# Start dev server (with backend proxy)
npm run dev

# Start dev server (standalone with mock API)
npm run dev:standalone
```

### Testing

```bash
# Run unit tests
npm test

# Watch mode
npm run test:watch

# Run tests with UI (interactive)
npm run test:ui

# Generate coverage report (~55%)
npm run test:coverage

# E2E Tests (Cypress)
npx cypress open              # Interactive mode
npx cypress run               # Headless mode
npm run test:e2e              # Run E2E tests
```

### Build & Preview

```bash
# Build for production
npm run build

# Preview production build
npm run preview

# Format code
npm run format

# Lint code
npm run lint
```

### Development Modes

Das Frontend unterstützt **3 Entwicklungsmodi** (siehe [DEVELOPMENT-MODES.md](DEVELOPMENT-MODES.md)):

1. **Backend Mode** (Standard) - Proxy zu lokalem Backend auf Port 8000
2. **Standalone Mode** - Mock API für isolierte Frontend-Entwicklung
3. **Production Mode** - Build für Deployment

```bash
# Backend Mode (default)
npm run dev
# → http://localhost:5173 + Proxy zu localhost:8000/api

# Standalone Mode (kein Backend nötig)
npm run dev:standalone
# → http://localhost:5173 + Mock API

# Production Build
npm run build
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/       # Reusable UI Components
│   │   ├── EmptyState.jsx
│   │   ├── DeviceSwiper.jsx
│   │   ├── Navigation.jsx
│   │   └── ErrorBoundary.jsx
│   ├── pages/            # Page Components (React Router)
│   │   ├── RadioPresets.jsx      # Radio Preset Management
│   │   ├── LocalControl.jsx      # Volume, Playback, Source Control
│   │   ├── MultiRoom.jsx         # Zone Management
│   │   ├── Firmware.jsx          # Device Info & Firmware Status
│   │   ├── Settings.jsx          # App & Device Configuration
│   │   └── Licenses.jsx          # OSS Licenses
│   ├── services/         # Service Layer (Clean Architecture)
│   │   ├── deviceService.js      # Device API abstraction
│   │   └── mockDeviceService.js  # Mock implementation for testing
│   ├── hooks/            # Custom React Hooks
│   │   ├── useDevices.js         # Device state management
│   │   └── useRadioSearch.js     # Radio search logic
│   ├── App.jsx           # Main Application Component
│   └── main.jsx          # Entry Point (React Render)
├── tests/                # Unit & Component Tests (87 tests)
│   ├── setup.js          # Vitest configuration
│   ├── App.test.jsx
│   ├── EmptyState.test.jsx
│   ├── Licenses.test.jsx
│   └── services/
│       └── deviceService.test.js
├── cypress/              # E2E Tests (15 tests)
│   ├── e2e/
│   │   └── app.cy.js
│   └── support/
│       └── commands.js
├── public/               # Static Assets (Favicon, Icons)
├── vite.config.js        # Vite Build Configuration
├── vitest.config.js      # Vitest Test Configuration
└── cypress.config.js     # Cypress E2E Configuration
```

## API Integration

### Backend API Endpoints

Das Frontend kommuniziert mit dem CloudTouch Backend über:

**Devices**:
- `GET /api/devices` - Liste aller Geräte
- `POST /api/devices/sync` - Gerätesuche & DB-Sync triggern
- `GET /api/devices/{id}` - Gerätedetails
- `GET /api/devices/{id}/capabilities` - Device Capabilities
- `DELETE /api/devices/{id}` - Gerät löschen (production-guarded)

**Radio**:
- `GET /api/radio/search?type=name&query=rock&limit=10` - Radiosender suchen
- `GET /api/radio/station/{uuid}` - Station Details

**Settings**:
- `GET /api/settings/manual-ips` - Manuelle IP-Konfiguration
- `POST /api/settings/manual-ips` - Bulk IP-Update

### Service Layer

Alle API-Calls laufen über `src/services/deviceService.js`:

```javascript
import { getDevices, discoverDevices } from './services/deviceService.js';

// In Component:
const devices = await getDevices();
const discovered = await discoverDevices();
```

**Vorteile**:
- Clean Architecture (Service abstrahiert API)
- Testbar (Mock-Service für Tests)
- Error Handling zentral
- Retry-Logik

## Architecture Principles

### Component Hierarchy

```
App.jsx (Root)
├── Navigation (Persistent)
├── DeviceSwiper (Device Selection)
└── Router (React Router)
    ├── RadioPresets (Page)
    ├── LocalControl (Page)
    ├── MultiRoom (Page)
    ├── Firmware (Page)
    ├── Settings (Page)
    └── Licenses (Page)
```

### State Management

- **Device State**: `useDevices` Hook (src/hooks/useDevices.js)
- **Local State**: React useState für UI-State
- **No Global State**: Kein Redux/Zustand (bewusste Entscheidung)
- **Props Passing**: Device-Prop von App → Pages

### Error Handling

- Loading States: Spinner während API-Calls
- Error States: Fehlermeldungen mit Retry-Button
- Empty States: Hilfreiche Anleitung bei 0 Geräten
- Network Errors: Automatische Retry-Logik (deviceService)

## Migration von Original-Frontend

Das Original-Frontend wurde nach `frontend-archive/frontend-original/` verschoben.
Die Swipe-Variante aus `prototypes/soundtouch-spa-swipe/` ist jetzt das produktive Frontend.

### Wichtigste Änderungen (Iteration 2.5):

1. **Service Layer** extrahiert (deviceService.js)
2. **87 Tests** hinzugefügt (~55% Coverage)
3. **15 E2E Tests** mit Cypress
4. **Global State** entfernt (Lock-based Discovery)
5. **Error Handling** mit Retry-Button
6. **Empty State** beim ersten Start
7. **Licenses-Seite** für OSS Compliance
8. **Device Prop Passing** für Datenkonsistenz
9. **Production Guards** für DELETE-Endpoints

## Troubleshooting

### Tests schlagen fehl

```bash
# Cache leeren
rm -rf node_modules/.vite

# Dependencies neu installieren
npm ci

# Tests mit ausführlicher Ausgabe
npm test -- --reporter=verbose
```

### Dev-Server startet nicht

```bash
# Port bereits belegt? Ändere in vite.config.js:
server: { port: 5174 }

# Oder beende Port 5173:
# Windows: netstat -ano | findstr :5173
# Linux/Mac: lsof -ti:5173 | xargs kill
```

### Backend nicht erreichbar

```bash
# Backend läuft? Prüfe http://localhost:8000/health
curl http://localhost:8000/health

# Proxy-Konfiguration in vite.config.js prüfen
# Standalone-Mode nutzen ohne Backend:
npm run dev:standalone
```

## Contributing

Siehe [../CONTRIBUTING.md](../CONTRIBUTING.md) für:
- React Coding Standards
- Component Naming (PascalCase)
- Testing Guidelines
- Commit Message Format

## License

Apache License 2.0 - Siehe [../LICENSE](../LICENSE)

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## License

MIT License - siehe [Licenses](/licenses) Page in der App

---

**CloudTouch** - Lokale Steuerung für Bose SoundTouch
