# Git Tracking Policy

**Erstellt**: 2026-03-06  
**Zweck**: Kategorisierung aller Workspace-Dateien hinsichtlich Git-Tracking  
**Basis**: Scan des Workspace nach `git filter-repo` Bereinigung (Commit `f9b35ca`)

---

## Legende

| Symbol | Kategorie | Bedeutung |
|--------|-----------|-----------|
| ✅ | **MUSS** | Muss zwingend in Git sein |
| ❌ | **NIE** | Darf niemals in Git sein |
| ❓ | **UNSICHER** | Entscheidung erforderlich |

---

## ✅ MUSS in Git

### Quellcode

| Pfad | Begründung |
|------|------------|
| `apps/backend/src/opencloudtouch/` | Gesamter Backend-Quellcode |
| `apps/backend/adapters/` | Bose SoundTouch Adapter |
| `apps/backend/tests/` | Backend-Tests (Unit + Integration + Regression) |
| `apps/frontend/src/` | Gesamter Frontend-Quellcode |
| `apps/frontend/tests/` | Frontend-Tests (Unit + E2E Cypress-Specs) |
| `apps/frontend/public/` | Statische Assets (SVGs, Icons, HTML-Templates) |

### Build & Deployment

| Pfad | Begründung |
|------|------------|
| `Dockerfile` | Container-Build-Definition |
| `deployment/docker-compose.yml` | Docker Compose für Produktion |
| `deployment/local/deploy-local.ps1` | Lokales Deployment-Script |
| `deployment/local/deploy-to-server.ps1` | TrueNAS-Deployment-Script |
| `deployment/local/export-image.ps1` | Image-Export-Script |
| `deployment/local/run-real-tests.ps1` | Echte Hardware-Tests |
| `deployment/local/.env.template` | Umgebungsvariablen-Template |
| `deployment/local/config.ps1` | Deployment-Konfiguration |
| `deployment/local/clear-database.ps1` | DB-Reset-Script |
| `deployment/local/emergency-cleanup.ps1` | Notfall-Cleanup |
| `deployment/local/run-e2e-tests-remote.ps1` | Remote E2E Runner |
| `deployment/README.md`, `deployment/LOCAL-DEPLOYMENT.md` | Deployment-Dokumentation |

### Konfiguration & Standards

| Pfad | Begründung |
|------|------------|
| `.gitignore` | Git-Ausschlussregeln |
| `.gitattributes` | Line-Ending-Normalisierung |
| `.pre-commit-config.yaml` | Pre-commit Hook-Konfiguration |
| `.pre-commit-config-hooks/check-git-user.py` | Hook-Script |
| `.prettierrc`, `.prettierignore` | Code-Formatierung |
| `.dockerignore` | Docker-Build-Ausschlüsse |
| `.commitlintrc.json` | Commit-Nachrichtenformat |
| `config.example.yaml` | Konfigurationstemplate (KEINE Secrets!) |
| `.env.template` | Umgebungsvariablen-Template (Root) |
| `codecov.yml` | Code-Coverage-Konfiguration |
| `package.json`, `package-lock.json` | Node.js-Abhängigkeiten |
| `apps/backend/pyproject.toml` | Python-Projektdefinition |
| `apps/backend/requirements*.txt` | Python-Abhängigkeiten |
| `apps/frontend/package.json`, `apps/frontend/package-lock.json` | Frontend-Abhängigkeiten |
| `apps/frontend/vite.config.ts` | Vite-Build-Konfiguration |
| `apps/frontend/tsconfig*.json` | TypeScript-Konfiguration |
| `apps/frontend/.eslintrc.json` | ESLint-Konfiguration |
| `apps/frontend/.prettierrc` | Frontend Prettier |
| `.vscode/settings.json` | VS Code-Workspace-Einstellungen |

### CI/CD

| Pfad | Begründung |
|------|------------|
| `.github/workflows/ci-cd.yml` | Haupt-CI/CD-Pipeline |
| `.github/workflows/commitlint.yml` | Commit-Lint-Workflow |
| `.github/workflows/release.yml` | Release-Automation |
| `.github/dependabot.yml` | Abhängigkeits-Updates |
| `scripts/` | Automation-Scripts (Hooks, E2E-Runner etc.) |

### Dokumentation (öffentlich)

| Pfad | Begründung |
|------|------------|
| `README.md` | Projekt-Einstieg |
| `CHANGELOG.md` | Versionshistorie |
| `CONTRIBUTING.md` | Beitragsrichtlinien |
| `SECURITY.md` | Sicherheitsrichtlinien |
| `LICENSE`, `NOTICE`, `TRADEMARK.md` | Rechtliche Dokumente |
| `docs/API.md` | API-Referenz |
| `docs/CONFIGURATION.md` | Konfigurationsdokumentation |
| `docs/TESTING.md` | Test-Dokumentation |
| `docs/GIT_HOOKS.md` | Hook-Dokumentation |
| `docs/TROUBLESHOOTING.md` | Fehlerbehebung |
| `docs/SSH_QUICKSTART.md` | SSH-Schnellstart |
| `docs/CONVENTIONAL_COMMITS.md` | Commit-Format |
| `docs/DEPENDENCY-MANAGEMENT.md` | Abhängigkeitsverwaltung |
| `docs/BLOCKING_NO_VERIFY.md` | No-Verify-Sperre-Dokumentation |
| `docs/LICENSES_*.md` | Lizenzübersichten |
| `docs/PRESET_PLAYBACK.md` | Preset-Playback-Dokumentation |
| `docs/adr/` | Architecture Decision Records |
| `apps/backend/README.md` | Backend-Dokumentation |
| `apps/frontend/README.md` | Frontend-Dokumentation |
| `apps/frontend/DEVELOPMENT-MODES.md` | Entwicklungs-Modi |

### Bose API Referenz (öffentliche Schemas)

| Pfad | Begründung |
|------|------------|
| `apps/backend/bose_api/device_schemas/` | 153 XML-Schema-Dateien (öffentlich recherchiert) |
| `apps/backend/bose_api/README.md` | API-Übersicht |
| `apps/backend/bose_api/SCHEMA_DIFFERENCES.md` | Schema-Unterschiede |
| `apps/backend/bose_api/2025.12.18 SoundTouch Web API.pdf` | Originaldokumentation |
| `apps/backend/bose_api/PRESET_ANALYSIS_OCT.md` | Preset-Analyse |
| `apps/backend/bose_api/TEST_RESULTS_PRESET_COMPARISON.md` | Testergebnisse |
| `apps/backend/bose_api/analyze_api.py` | API-Analyse-Script |
| `apps/backend/bose_api/compare_api_sources.py` | Schema-Vergleich |
| `apps/backend/bose_api/consolidate_schemas.py` | Schema-Konsolidierung |
| `apps/backend/bose_api/preset_*.xml` | Beispiel-Preset-Daten (anonymisiert) |

---

## ❌ NIE in Git

### Persönliche AI-Agent-Konfiguration

| Pfad | Begründung |
|------|------------|
| `AGENTS.md` | Persönliche AI-Entwicklungsrichtlinien — in `.gitignore` |
| `.github/AGENT_PROMPT_TEMPLATES.md` | AI-Prompt-Templates — **aktuell verfolgt! → bereinigen** |
| `.github/AGENT_TASK_PROTOCOL.md` | AI-Task-Protokoll — **aktuell verfolgt! → bereinigen** |

### Lokale Entwicklungstools

| Pfad | Begründung |
|------|------------|
| `tools/local-scripts/` | Persönliche Automatisierungsscripts — in `.gitignore` |
| `tools/firmware_branch_scanner.py` | Persönliches Analyse-Tool — in `.gitignore` |
| `tools/Prepare-SoundTouchUSB.ps1` | Persönliches Device-Script — in `.gitignore` |
| `tools/soundtouch-post-ssh.sh` | Persönliches SSH-Script — in `.gitignore` |
| `tools/Test-SoundTouchSSH.ps1` | Persönliches Test-Script — in `.gitignore` |

### Persönliche Analyse & Planung

| Pfad | Begründung |
|------|------------|
| `docs/analysis/` | Persönliche Forschungsnotizen — in `.gitignore` |
| `docs/project-planning/` | Persönlicher Roadmap/Planungsordner — in `.gitignore` |
| `reference-impl/` | Persönliche Referenzimplementierungen — in `.gitignore` |

### Secrets & Lokale Konfiguration

| Pfad | Begründung |
|------|------------|
| `.env`, `.env.local` | Secrets — in `.gitignore` |
| `deployment/local/.env` | Lokale Deployment-Secrets — in `.gitignore` |
| `config.yaml` | Lokale Konfiguration mit Secrets — in `.gitignore` |
| `docker-compose.override.yml` | Lokale Overrides — in `.gitignore` |
| `apps/frontend/.env.development.local` | Lokale Entwicklungs-Env (enthält private IPs) |

### Laufzeit-Daten & Datenbanken

| Pfad | Begründung |
|------|------------|
| `data-local/` | Lokale SQLite-Datenbank — in `.gitignore` |
| `deployment/data-local/` | Container-Laufzeitdaten — in `.gitignore` |
| `*.db`, `*.db-journal` | Datenbankdateien — in `.gitignore` |

### Build-Artefakte

| Pfad | Begründung |
|------|------------|
| `apps/frontend/dist/` | Vite-Build-Output — in `.gitignore` |
| `apps/frontend/coverage/` | Test-Coverage-Reports — in `.gitignore` |
| `htmlcov/` | Python Coverage HTML — in `.gitignore` |
| `.venv/` | Python Virtual Environment — in `.gitignore` |
| `apps/frontend/node_modules/` | Node.js-Abhängigkeiten — in `.gitignore` |
| `*.tar` | Container-Image-Exports — in `.gitignore` |

### Test-Artefakte

| Pfad | Begründung |
|------|------------|
| `apps/frontend/tests/e2e/screenshots/` | Cypress Screenshots — in `.gitignore` |
| `apps/frontend/tests/e2e/reports/` | Cypress Reports — in `.gitignore` |
| `cypress-output.txt`, `e2e-result.txt` etc. | Test-Ausgabedateien — in `.gitignore` |
| `*_TEMP.md` | Temporäre Dokumente — in `.gitignore` |

---

## ❓ UNSICHER — Entscheidung erforderlich

### Gerätespezifische Bose API Dateien mit persönlichen Daten

| Pfad | Problem | Empfehlung |
|------|---------|------------|
| `apps/backend/bose_api/device_info_wohnzimmer.xml` | Enthält echten Gerätenamen "Wohnzimmer" und Netzwerkinformationen | Anonymisieren oder entfernen |
| `apps/backend/bose_api/preset_list_wohnzimmer.xml` | Enthält persönliche Preset-Konfiguration | Anonymisieren oder entfernen |
| `apps/backend/bose_api/current_preset_list.xml` | Aktueller Preset-Status eines echten Geräts | Anonymisieren oder entfernen |
| `apps/backend/bose_api/current_preset_list_prettified.xml` | Wie oben (formatierte Version) | Anonymisieren oder entfernen |

### GitHub Agent-Dateien

| Pfad | Problem | Empfehlung |
|------|---------|------------|
| `.github/AGENT_PROMPT_TEMPLATES.md` | Persönliche AI-Arbeitsablauf-Dokumentation im öffentlichen `.github/` | Entweder nach `NIE` verschieben und zu `.gitignore` hinzufügen, oder in neutrale Projekt-Dokumentation umschreiben |
| `.github/AGENT_TASK_PROTOCOL.md` | Wie oben | Wie oben |

### CI-Konfigurationsdateien

| Pfad | Problem | Empfehlung |
|------|---------|------------|
| `.ci-config.json` | Unklarer Zweck - CI-spezifische Schalter? | Prüfen ob öffentlich sicher |
| `.ci-config.md` | Dokumentation für `.ci-config.json` | Prüfen ob öffentlich sicher |

### Hardware-spezifische Tools

| Pfad | Problem | Empfehlung |
|------|---------|------------|
| `tools/pi4-usb-gadget/` | USB-Gadget-Setup für Raspberry Pi 4 — könnte Community-Nutzen haben | Entweder in `NIE` (aktuell gitignored) lassen oder als öffentliche Dokumentation freigeben |
| `tools/pi-zero-usb-gadget/` | Wie oben für Pi Zero | Wie oben |

### Frontend Entwicklungs-Umgebung

| Pfad | Problem | Empfehlung |
|------|---------|------------|
| `apps/frontend/.env.development.local` | Enthält lokale API-URLs (kann private IPs enthalten) | In `.gitignore` aufnehmen, Template erstellen |
| `apps/frontend/.env.production` | Enthält Production-API-Konfiguration | Prüfen ob Secrets, ggf. als Template |

---

## Zusammenfassung

| Kategorie | Anzahl (geschätzt) | Status |
|-----------|--------------------|--------|
| ✅ MUSS in Git | ~470 Dateien | Korrekt verfolgt |
| ❌ NIE in Git | ~80+ Dateien | Korrekt gitignored (nach filter-repo Bereinigung) |
| ❓ UNSICHER | 10 Dateien | Entscheidung ausstehend |

### Empfohlene nächste Schritte

1. **Gerätedaten anonymisieren**: `device_info_wohnzimmer.xml`, `preset_list_wohnzimmer.xml`, `current_preset_list*.xml` — Gerätenamen und Netzwerkdaten ersetzen
2. **Agent-Dateien entscheiden**: `.github/AGENT_PROMPT_TEMPLATES.md` und `.github/AGENT_TASK_PROTOCOL.md` — entweder löschen/gitignoren oder für Community aufbereiten
3. **Frontend `.env` prüfen**: `apps/frontend/.env.development.local` und `.env.production` auf Secrets prüfen
4. **`.ci-config.*` prüfen**: Sicherstellen dass keine internen Infrastrukturdetails enthalten sind

---

*Letzte Überprüfung: 2026-03-06 | Nach git filter-repo Bereinigung (f9b35ca)*
