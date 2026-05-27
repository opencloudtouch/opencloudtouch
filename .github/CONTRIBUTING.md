# Contributing to OpenCloudTouch

Vielen Dank für dein Interesse an OpenCloudTouch! 🎉

---

## 🚀 Quick Start für Contributors

### 1. Repository Setup

```bash
# Fork & Clone
git clone https://github.com/<your-username>/soundtouch-bridge.git
cd soundtouch-bridge

# Upstream hinzufügen
git remote add upstream https://github.com/user/soundtouch-bridge.git
```

### 2. Development Environment Setup

#### **Backend (Python 3.11+)**
```bash
cd apps/backend

# Virtual Environment (empfohlen)
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\Activate.ps1  # Windows

# Dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### **Frontend (Node.js 20+)**
```bash
cd apps/frontend
npm ci
```

### 3. **Git Hooks installieren (WICHTIG!)**

**Windows (PowerShell):**
```powershell
.\scripts\install-hooks.ps1
```

**Linux/Mac (Bash):**
```bash
chmod +x scripts/install-hooks.sh
./scripts/install-hooks.sh
```

**Was passiert?**
- ✅ Commit-Message Validierung (Conventional Commits)
- ✅ Auto-Formatierung (black, prettier)
- ✅ Linting (ruff, eslint)
- ✅ Security Checks (bandit)
- ✅ Unit Tests vor Push

📖 Details: [docs/GIT_HOOKS.md](docs/GIT_HOOKS.md)

---

## 📝 Commit-Richtlinien

Wir verwenden **[Conventional Commits](https://www.conventionalcommits.org/)** für automatische Changelogs und Versioning.

### Format:
```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Beispiele:
```bash
feat(devices): add SSDP auto-discovery
fix(api): handle null response in device sync
docs(readme): update installation instructions
test(backend): add regression test for XML parsing
perf(docker): optimize arm64 build time
```

### Wichtigste Types:
- `feat:` - Neue Feature
- `fix:` - Bugfix
- `docs:` - Dokumentation
- `test:` - Tests
- `refactor:` - Code-Refactoring
- `perf:` - Performance
- `ci:` - CI/CD
- `chore:` - Maintenance

📖 Komplett Guide: [docs/CONVENTIONAL_COMMITS.md](docs/CONVENTIONAL_COMMITS.md)

**Git Hooks prüfen automatisch deine Commits!**

---

## 🧪 Testing

### Backend Tests
```bash
cd apps/backend

# Alle Tests
pytest -v

# Mit Coverage
pytest --cov=opencloudtouch --cov-report=html

# Nur Unit Tests (schnell)
pytest tests/unit -v

# Nur Integration Tests
pytest tests/integration -v
```

**Minimum Coverage**: 80% (wird von CI geprüft)

### Frontend Tests
```bash
cd apps/frontend

# Unit Tests
npm test

# Mit Coverage
npm run test:coverage

# Watch Mode
npm run test:watch

# E2E Tests (benötigt laufendes Backend)
npm run test:e2e
```

### E2E Tests
```bash
# Backend starten
cd apps/backend
PYTHONPATH=src OCT_MOCK_MODE=true uvicorn opencloudtouch.main:app --port 7778 &

# Frontend starten
cd apps/frontend
npm run preview -- --port 4173 &

# E2E Tests
npm run test:e2e
```

### UX-Screenshot-Tests & Accessibility-Audit (bei UI-Änderungen)

**Pflicht** für jede Story/Task, die UI-Komponenten hinzufügt oder verändert:

```bash
# 1. UX-Screenshots aktualisieren (baut + startet Preview-Server automatisch)
npm run test:ux
# Output: apps/frontend/tests/e2e/screenshots/ux/**/*.png (dark + light)

# 2. WCAG 2.1 AA Accessibility-Audit
npm run audit:a11y
# Report: apps/frontend/tests/e2e/reports/accessibility/accessibility-report.md

# 3. GPT-4o Vision-Analyse (bei ≥3 geänderten UI-Komponenten)
#    Voraussetzung: GITHUB_TOKEN_COPILOT in .env
npm run audit:vision
# Report: apps/frontend/tests/e2e/reports/vision/ux-vision-report.md
```

**Neue Findings** (Kontrast, Touch-Target, Accessibility-Violations) in
`docs/project-planning/phases/phase-3b-quality-sprint-1b/REFACTORING.md` eintragen.

---

## 🔧 Development Workflow

### 1. **Feature Branch erstellen**
```bash
git checkout -b feat/my-new-feature
```

### 2. **Code schreiben + Tests**
```bash
# Backend
cd apps/backend
# ... code changes ...
pytest tests/

# Frontend
cd apps/frontend
# ... code changes ...
npm test
```

### 3. **UX-Audit (nur bei UI-Änderungen)**
```bash
# Screenshots aktualisieren
npm run test:ux

# Accessibility-Audit (WCAG 2.1 AA)
npm run audit:a11y

# Vision-Analyse (optional, bei größeren UI-Änderungen)
# Voraussetzung: GITHUB_TOKEN_COPILOT in .env
npm run audit:vision
```

Findings in `docs/project-planning/phases/phase-3b-quality-sprint-1b/REFACTORING.md` eintragen.

### 4. **Commit (Hooks laufen automatisch!)**
```bash
git add .
git commit -m "feat(devices): add multiroom support"

# Hooks prüfen:
# ✅ Commit-Message Format
# ✅ Code-Formatierung
# ✅ Linting
# ✅ Security
```

### 5. **Push (Tests laufen automatisch!)**
```bash
git push origin feat/my-new-feature

# Hook prüft:
# ✅ Unit Tests
```

### 6. **Pull Request erstellen**
- Gehe zu GitHub
- Erstelle PR von deinem Branch → `main`
- Beschreibe Änderungen
- Warte auf CI/CD Checks

### 7. **CI/CD Pipeline (automatisch)**
GitHub Actions führt aus:
1. ✅ Security Scan (bandit, npm audit)
2. ✅ Format Check (black, prettier)
3. ✅ Lint (ruff, eslint)
4. ✅ Backend Tests (pytest, 80% coverage)
5. ✅ Frontend Tests (vitest)
6. ✅ E2E Tests (Cypress)
7. ✅ Commit Message Validation

**Nur wenn alles grün ist**, kann PR gemerged werden!

---

## 📐 Code Style

### Backend (Python)
- **Formatter**: `black` (automatisch via pre-commit hook)
- **Linter**: `ruff`
- **Type Hints**: PFLICHT für alle Public Functions
- **Docstrings**: Google Style
- **Max Line Length**: 100

```python
def discover_devices(timeout: int = 10) -> List[Device]:
    """Discover SoundTouch devices via SSDP.
    
    Args:
        timeout: Discovery timeout in seconds.
        
    Returns:
        List of discovered devices.
        
    Raises:
        DiscoveryError: If discovery fails.
    """
    pass
```

### Frontend (TypeScript/React)
- **Formatter**: `prettier` (automatisch via pre-commit hook)
- **Linter**: `eslint`
- **Components**: Functional Components + Hooks
- **Props**: TypeScript Interfaces
- **CSS**: CSS Modules

```tsx
interface DeviceCardProps {
  device: Device;
  onSelect: (device: Device) => void;
}

export function DeviceCard({ device, onSelect }: DeviceCardProps) {
  return <div>...</div>;
}
```

---

## 🏗️ Architektur

### Backend (Clean Architecture)
```
apps/backend/src/opencloudtouch/
├── api/              # FastAPI Routes
├── domain/           # Domain Models (Entities)
├── devices/          # Device Management
│   ├── adapter.py    # Bose SoundTouch Adapter
│   ├── repository.py # Device Persistence
│   └── routes.py     # Device API
├── providers/        # Music/Radio Providers
└── core/             # Config, Logging, DB
```

**Regeln**:
- Domain darf keine externen Dependencies haben
- Adapter wrappen externe APIs
- Repository für alle DB-Zugriffe
- Use Cases enthalten Business Logic

### Frontend (Feature-Based)
```
apps/frontend/src/
├── components/       # Reusable UI Components
├── features/         # Feature Modules
│   ├── devices/
│   ├── radio/
│   └── nowplaying/
├── services/         # API Clients
└── utils/            # Helpers
```

📖 Architektur-Details: [docs/OpenCloudTouch_Projektplan.md](docs/OpenCloudTouch_Projektplan.md)

---

## 🐛 Bug Reports

**Bevor du einen Bug reportest:**
1. Prüfe ob Issue schon existiert
2. Reproduziere in latest Version
3. Sammle Logs

**Issue Template:**
```markdown
## Bug Description
Kurze Beschreibung

## Steps to Reproduce
1. Starte Container
2. Öffne UI
3. Klicke auf...

## Expected Behavior
Was sollte passieren?

## Actual Behavior
Was passiert tatsächlich?

## Environment
- OS: Windows 11 / Ubuntu 22.04 / macOS 14
- Docker Version: 24.0.7
- OCT Version: v0.2.0
- Browser: Chrome 120

## Logs
```
[Paste logs here]
```
```

---

## 💡 Feature Requests

**Template:**
```markdown
## Feature Description
Kurze Beschreibung der gewünschten Funktion

## Use Case
Warum brauchst du das?

## Proposed Solution
Wie könnte es umgesetzt werden?

## Alternatives
Andere Ansätze?
```

---

## 🔐 Security

**Sicherheitslücken bitte NICHT öffentlich melden!**

Kontakt: `security@<your-domain>` oder GitHub Security Advisory

---

## 🌍 Translations (i18n)

OpenCloudTouch uses [react-i18next](https://react.i18next.com/) for internationalization.
See [docs/adr/007-i18n.md](../docs/adr/007-i18n.md) for the full library decision.

### Source of Truth

**`apps/frontend/src/i18n/locales/en.json` is the single source of truth for all UI strings.**

Rules:
- Every user-visible string MUST exist in `en.json` before it appears in any component
- German translation lives in `de.json` and must be kept in sync
- New strings go to `en.json` first, then are translated in `de.json` (and any other locale)
- Never hardcode English text directly in components — always use `t("key")`

### Adding a new UI string

1. Add the key to `apps/frontend/src/i18n/locales/en.json`
2. Add the German translation to `apps/frontend/src/i18n/locales/de.json`
3. Add translations for any other supported locales (`fr.json`, `it.json`, …)
4. Use `const { t } = useTranslation()` + `t("your.new.key")` in the component

### Contributing a new language

Use the **[Translation Contribution](https://github.com/opencloudtouch/opencloudtouch/issues/new?template=translation_contribution.yml)** issue template.
You do not need to open a PR — paste your translated JSON into the issue and a maintainer will create the locale file.

---

## 📚 Dokumentation

Bei Code-Änderungen bitte auch Doku aktualisieren:
- **README.md** - User-facing Features
- **Backend README** - API Änderungen
- **Frontend README** - Component Changes
- **CHANGELOG.md** - Bei Release (automatisch)

---

## ✅ Pull Request Checklist

Bevor du PR erstellst:
- [ ] Tests grün (`pytest -v` + `npm test`)
- [ ] Coverage ≥ 80%
- [ ] Code formatiert (`black` + `prettier`)
- [ ] Linting OK (`ruff` + `eslint`)
- [ ] Commit Messages Conventional Format
- [ ] Dokumentation aktualisiert
- [ ] E2E Tests passen (falls UI-Änderung)
- [ ] `npm run test:ux` ausgeführt, Screenshots aktuell (falls UI-Änderung)
- [ ] `npm run audit:a11y` grün / keine neuen Violations (falls UI-Änderung)
- [ ] CHANGELOG.md aktualisiert (bei Breaking Changes)

**GitHub Actions prüft automatisch!**

---

## 🎓 Learning Resources

### Backend
- **FastAPI**: https://fastapi.tiangolo.com/
- **Pytest**: https://docs.pytest.org/
- **Clean Architecture**: https://blog.cleancoder.com/

### Frontend
- **React**: https://react.dev/
- **Vite**: https://vitejs.dev/
- **Vitest**: https://vitest.dev/

### DevOps
- **Docker**: https://docs.docker.com/
- **GitHub Actions**: https://docs.github.com/en/actions
- **Pre-commit**: https://pre-commit.com/

---

## 🤝 Code Review

**Als Reviewer achte auf:**
- ✅ Tests vorhanden & sinnvoll
- ✅ Keine Magic Numbers
- ✅ Sprechende Variablen-Namen
- ✅ Error Handling
- ✅ Keine Code-Duplikation
- ✅ Performance-Implikationen
- ✅ Security (SQL Injection, XSS, etc.)

**Als Author:**
- Beschreibe **Warum** nicht nur **Was**
- Verlinke Issues
- Zeige Screenshots bei UI-Änderungen
- Markiere Breaking Changes

---

## 📞 Kontakt

- **GitHub Issues**: https://github.com/user/soundtouch-bridge/issues
- **Discussions**: https://github.com/user/soundtouch-bridge/discussions
- **Discord**: (coming soon)

---

## 📜 Lizenz

Mit deinem Beitrag stimmst du zu dass dein Code unter der **MIT License** veröffentlicht wird.

Siehe [LICENSE](LICENSE) für Details.

---

**Danke fürs Mitmachen! 🎉**
