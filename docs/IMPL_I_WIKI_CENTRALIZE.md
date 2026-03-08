# Implementierungsdokument I — "Wiki-First + Zentralisierung"

> **Voraussetzungen**: GitHub-Zugang mit Wiki-Berechtigung für das Repo  
> **Zeit**: 5–6 Stunden  
> **Risiko**: Mittel — Dockerfile-COPY und CI/CD-Pfade werden geändert

---

## Phase 1 — GitHub Wiki einrichten (30 Min)

### 1.1 Wiki aktivieren

Im GitHub Repository: **Settings → Features → Wikis → aktivieren**

### 1.2 Wiki klonen

```powershell
# GitHub Wiki ist ein separates Git-Repo
git clone https://github.com/scheilch/opencloudtouch.wiki.git C:\DEV\private\soundtouch-bridge.wiki
cd C:\DEV\private\soundtouch-bridge.wiki
```

### 1.3 Alle docs/ Dateien ins Wiki migrieren

```powershell
# Aus dem Repo-Root:
$wikiPath = "C:\DEV\private\soundtouch-bridge.wiki"
$docsPath = "C:\DEV\private\soundtouch-bridge\docs"

# Jeden docs/-Inhalt ins Wiki kopieren (ADRs als Unterordner)
Copy-Item "$docsPath\*.md" $wikiPath
New-Item -ItemType Directory -Force "$wikiPath\adr"
Copy-Item "$docsPath\adr\*.md" "$wikiPath\adr"

# Nicht migrieren (bleibt im Repo):
# - WORKSPACE_ANALYSIS.md (dieses Analyse-Dokument)
# - IMPL_*.md (Implementierungsdokumente)
```

### 1.4 Wiki-Navigation erstellen

```powershell
# _Sidebar.md erstellt die linke Navigation im GitHub Wiki
@'
## OpenCloudTouch Docs

**Getting Started**
- [[Home]]
- [[CONFIGURATION|Konfiguration]]
- [[TROUBLESHOOTING|Troubleshooting]]

**Development**
- [[TESTING|Testing]]
- [[CONVENTIONAL_COMMITS|Commit-Konventionen]]
- [[GIT_HOOKS|Git Hooks]]
- [[DEPENDENCY-MANAGEMENT|Dependencies]]
- [[BLOCKING_NO_VERIFY|No-Verify Verbot]]

**API & Architektur**
- [[API|REST API]]
- [[adr/001-clean-architecture|ADR 001 Clean Architecture]]
- [[adr/002-fastapi-app-state|ADR 002 FastAPI App State]]
- [[adr/003-ssdp-discovery|ADR 003 SSDP Discovery]]
- [[adr/004-react-typescript-vite|ADR 004 React/TS/Vite]]

**Deployment**
- [[SSH_QUICKSTART|SSH Quickstart]]

**Legal**
- [[LICENSES_ALL|Alle Lizenzen]]
- [[LICENSES_BACKEND|Backend Lizenzen]]
- [[LICENSES_FRONTEND|Frontend Lizenzen]]
'@ | Set-Content "$wikiPath\_Sidebar.md"
```

### 1.5 Wiki committen und pushen

```powershell
cd C:\DEV\private\soundtouch-bridge.wiki
git add .
git commit -m "Initial wiki migration from docs/"
git push
```

### 1.6 Wiki-Link zu Root-README hinzufügen

In `README.md` am Anfang einen Wiki-Link ergänzen:
```markdown
> 📖 **Vollständige Dokumentation**: [GitHub Wiki](https://github.com/scheilch/opencloudtouch/wiki)
```

---

## Phase 2 — Artefakt-Zentralisierung (.out/) (2h)

### 2.1 `.out/` zu Root `.gitignore` hinzufügen

```powershell
Add-Content "C:\DEV\private\soundtouch-bridge\.gitignore" "`n# Centralized generated artifacts`n.out/`n"
```

### 2.2 Backend: Coverage → `.out/coverage/backend/`

In `apps/backend/pyproject.toml` am Ende ergänzen:

```toml
[tool.coverage.run]
data_file = "../../.out/coverage/backend/.coverage"
branch = true

[tool.coverage.report]
show_missing = true
fail_under = 80

[tool.coverage.html]
directory = "../../.out/coverage/backend/htmlcov"

[tool.coverage.xml]
output = "../../.out/coverage/backend/coverage.xml"
```

> **Pfad-Logik**: pytest läuft in `apps/backend/` → `../../` = Repo-Root

### 2.3 Frontend: Vitest Coverage → `.out/coverage/frontend/`

In `apps/frontend/vitest.config.ts`:
```typescript
coverage: {
  provider: 'v8',
  reporter: ['text', 'html', 'json-summary', 'lcov'],
  reportsDirectory: '../../.out/coverage/frontend',  // ← ergänzen
  // ... Rest unverändert
}
```

### 2.4 Frontend: Vite Build → `.out/dist/`

In `apps/frontend/vite.config.ts`:
```typescript
build: {
  outDir: '../../.out/dist',   // ← ergänzen oder anpassen
  emptyOutDir: true,
}
```

### 2.5 Dockerfile anpassen (kritisch!)

Der aktuelle Dockerfile COPY-Befehl erwartet `apps/frontend/dist`:
```dockerfile
# ALT:
COPY --from=frontend-builder /app/apps/frontend/dist ./frontend/dist

# NEU:
COPY --from=frontend-builder /app/.out/dist ./frontend/dist
```

```powershell
# In Dockerfile ändern:
(Get-Content "C:\DEV\private\soundtouch-bridge\Dockerfile") -replace `
  "COPY --from=frontend-builder /app/apps/frontend/dist ./frontend/dist", `
  "COPY --from=frontend-builder /app/.out/dist ./frontend/dist" | `
  Set-Content "C:\DEV\private\soundtouch-bridge\Dockerfile"
```

### 2.6 CI/CD: Coverage-Pfade anpassen

In `.github/workflows/ci-cd.yml` die zwei Stellen mit `apps/backend/coverage.xml` / `apps/backend/coverage.json` ändern:

```yaml
# ALT:
files: ./apps/backend/coverage.xml
path: apps/backend/coverage.json

# NEU:
files: ./.out/coverage/backend/coverage.xml
path: .out/coverage/backend/coverage.xml
```

### 2.7 E2E-Logs: `.out/e2e/`

In `scripts/e2e-runner.mjs` alle Output-Dateipfade auf `.out/e2e/` umbiegen:
```powershell
Select-String -Path "scripts\e2e-runner.mjs" -Pattern "e2e-.*\.txt|e2e-out|e2e-result|e2e-job|e2e-tail"
```
Alle gefundenen Pfade von `e2e-*.txt` auf `.out/e2e/*.txt` ändern.

### 2.8 Cypress Reports: `.out/reports/`

In `apps/frontend/cypress.config.ts` und den weiteren Cypress-Config-Dateien:
```typescript
screenshotsFolder: '../../.out/reports/screenshots',
videosFolder: '../../.out/reports/videos',
```

---

## Phase 3 — Cleanup (30 Min)

### 3.1 Toten Code entfernen

```powershell
cd C:\DEV\private\soundtouch-bridge
git rm -r apps/backend/adapters/
```

### 3.2 Redundante Sub-gitignores entfernen

```powershell
git rm apps/backend/.gitignore
git rm apps/backend/tests/e2e/.gitignore
```

### 3.3 Falsch platzierte Datei verschieben

```powershell
git mv apps/backend/docs/LICENSES_FRONTEND.md docs/LICENSES_FRONTEND.md
Remove-Item apps/backend/docs -Recurse -Force
```

### 3.4 `docs/` aufräumen

Da Docs nach Wiki migriert: `docs/` aus git tracking entfernen (physisch bleibt `.local/archive/`):
```powershell
# Alle Docs außer den Analyse-/Impl-Docs aus git entfernen
git rm docs/API.md docs/BLOCKING_NO_VERIFY.md docs/CONFIGURATION.md
git rm docs/CONVENTIONAL_COMMITS.md docs/DEPENDENCY-MANAGEMENT.md
git rm docs/GIT_HOOKS.md docs/GIT_TRACKING_POLICY.md
git rm docs/LICENSES_ALL.md docs/LICENSES_BACKEND.md docs/LICENSES_FRONTEND.md
git rm docs/PRESET_PLAYBACK.md docs/SSH_QUICKSTART.md docs/TESTING.md docs/TROUBLESHOOTING.md
git rm docs/USB_SETUP_LOG.md 2>$null  # Falls noch vorhanden
git rm -r docs/adr/

# Physisch archivieren
New-Item -ItemType Directory -Force ".local/archive/docs"
Move-Item docs/*.md .local/archive/docs/ -ErrorAction SilentlyContinue
Move-Item docs/adr .local/archive/docs/adr -ErrorAction SilentlyContinue
```

Was verbleibt in `docs/`:
- `WORKSPACE_ANALYSIS.md` (dieses Dokument)
- `IMPL_I_WIKI_CENTRALIZE.md` (dieses Impl-Doc)
- `IMPL_II_DEVCONTAINER.md`
- `IMPL_III_VOLUME_ISOLATION.md`

### 3.5 Root `.gitignore` konsolidieren

Nachdem `.out/` hinzugefügt und Sub-gitignores weg sind, die Einzel-Artefakt-Regeln entfernen
die jetzt durch `.out/` abgedeckt sind:

```
# Diese Zeilen können raus (alle durch .out/ abgedeckt):
htmlcov/
.coverage
coverage.xml
**/coverage/
**/dist/
**/coverage.json
cypress-output.txt
e2e-result.txt
e2e-job-out.txt
e2e-out.txt
e2e-tail.txt
apps/frontend/tests/e2e/reports
**/tests/e2e/screenshots/
**/tests/e2e/reports/vision/screenshots/
**/cypress/videos/
**/cypress/screenshots/
**/cypress/downloads/
```

---

## Phase 4 — Validierung (1h)

### 4.1 Docker Build testen

```powershell
docker build -t oct-test:latest .
# Muss: Stage "frontend-builder" → .out/dist existiert, COPY erfolgreich
```

### 4.2 Backend Tests + Coverage

```powershell
Push-Location apps/backend
python -m pytest tests/unit --cov=src/opencloudtouch --cov-report=html --cov-report=xml -x -q
Pop-Location

Test-Path ".out/coverage/backend/htmlcov/index.html"  # Muss: True
Test-Path ".out/coverage/backend/coverage.xml"        # Muss: True
```

### 4.3 Frontend Tests + Coverage

```powershell
Push-Location apps/frontend
npm run test:coverage
Pop-Location

Test-Path ".out/coverage/frontend/index.html"  # Muss: True
```

### 4.4 Frontend Build

```powershell
Push-Location apps/frontend
npm run build
Pop-Location

Test-Path ".out/dist/index.html"  # Muss: True
```

### 4.5 Root-Workspace Reinheitsprüfung

```powershell
# Nach allen Test-Läufen: was liegt im Root-Workspace?
Get-ChildItem "C:\DEV\private\soundtouch-bridge" -Depth 0 | Select-Object Name
# Erwartet: apps, deployment, docs, scripts, .github, .vscode, package.json, etc.
# NICHT erwartet: htmlcov, .coverage, e2e-*.txt
```

---

## Phase 5 — Commit

```powershell
git add .gitignore
git add apps/backend/pyproject.toml
git add apps/frontend/vitest.config.ts
git add apps/frontend/vite.config.ts
git add apps/frontend/cypress.config.ts
git add apps/frontend/cypress.audit.config.ts
git add apps/frontend/cypress.ux.config.ts
git add scripts/e2e-runner.mjs
git add Dockerfile
git add .github/workflows/ci-cd.yml
git add README.md

git status

git commit -m "chore(structure): centralize artifacts in .out/, migrate docs to wiki

- Remove apps/backend/adapters/ (dead code, zero imports)
- Remove apps/backend/.gitignore + apps/backend/tests/e2e/.gitignore (redundant)
- All generated artifacts → .out/ (coverage, dist, e2e-logs, reports)
- Dockerfile: COPY from /app/.out/dist instead of /app/apps/frontend/dist
- CI/CD: update coverage paths to .out/coverage/backend/
- docs/ → GitHub Wiki (archived to .local/archive/docs/)
- Root .gitignore: single .out/ rule replaces 15+ scattered artifact entries"
```

---

## Erfolgskriterien

- [ ] GitHub Wiki enthält alle migrierten Dokumente und ist öffentlich zugänglich
- [ ] Root-README verlinkt auf Wiki
- [ ] `.out/` erscheint NICHT in `git status` (gitignored)
- [ ] `docker build .` läuft durch (Frontend-COPY aus `.out/dist`)
- [ ] `python -m pytest --cov` schreibt nach `.out/coverage/backend/`
- [ ] `npm run test:coverage` schreibt nach `.out/coverage/frontend/`
- [ ] `npm run build` schreibt nach `.out/dist/`
- [ ] GitHub Actions CI/CD: Codecov-Upload findet `.out/coverage/backend/coverage.xml`
- [ ] Root-Workspace nach Build/Test: kein Artefakt-Noise
- [ ] Alle Unit-Tests grün
