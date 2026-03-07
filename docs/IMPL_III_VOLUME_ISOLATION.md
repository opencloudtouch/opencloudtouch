# Implementierungsdokument III — "Devcontainer + Wiki + Volume Isolation"

> **Voraussetzungen**: Szenario II vollständig abgeschlossen  
> **Zeit**: 7–8 Stunden gesamt (Szenario I + II + diese Phase)  
> **Ergebnis**: Host-Workspace = immer sauber. Nie wieder ein Artefakt auf dem Host.

---

## Was Szenario III anders macht als Szenario II

In Szenario II landen Artefakte in `.out/` — gitignored, aber auf dem Host sichtbar.  
In Szenario III: **Named Docker Volume** für `.out/`. Artefakte existieren nur im Container.

```
Szenario II:  Host: .out/coverage/backend/ .out/dist/ .out/e2e/   ← sichtbar (gitignored)
Szenario III: Host: --- (nichts)              ← Volume, nur im Container zugänglich
```

---

## Phase 10 — Volume Isolation konfigurieren

### 10.1 Konzept verstehen

Docker Named Volumes sind Container-verwaltete Speicher die:
- Nicht im Host-Filesystem sichtbar sind (kein Windows Explorer, kein `ls` auf Host)
- Nach `docker volume prune` weg sind (→ Artefakte sind ephemer, wie erwartet)
- Im Container normal als Verzeichnis zugänglich sind
- Von VS Code im Container transparent geöffnet werden können (HTML-Reports etc.)

### 10.2 `devcontainer.json` anpassen: Volume für `.out/`

```json
{
  "name": "OpenCloudTouch Dev",
  "image": "mcr.microsoft.com/devcontainers/python:1-3.13-bookworm",

  "features": {
    "ghcr.io/devcontainers/features/node:1": { "version": "20" }
  },

  "mounts": [
    "source=oct-artifacts,target=/workspace/.out,type=volume"
  ],

  "postCreateCommand": "mkdir -p /workspace/.out/coverage/backend /workspace/.out/coverage/frontend /workspace/.out/dist /workspace/.out/e2e /workspace/.out/reports && pip install -r apps/backend/requirements-dev.txt && npm ci && npm ci --prefix apps/frontend && pre-commit install",

  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.pylance",
        "charliermarsh.ruff",
        "esbenp.prettier-vscode",
        "dbaeumer.vscode-eslint",
        "vitest.explorer"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "editor.formatOnSave": true
      }
    }
  },

  "forwardPorts": [7777, 5173]
}
```

**Schlüssel**: `"source=oct-artifacts,target=/workspace/.out,type=volume"`  
→ `/workspace/.out/` im Container → Named Volume `oct-artifacts` → **Host sieht nichts**

### 10.3 `.out/` aus Root `.gitignore` NICHT entfernen

`.out/` bleibt in `.gitignore` — auch wenn es nie erzeugt wird.  
Das schützt vor versehentlichen Commits falls jemand außerhalb des Containers arbeitet.

---

## Phase 11 — CI/CD: Volume-Setup betrifft CI NICHT

**Wichtig**: GitHub Actions läuft NICHT in deinem Devcontainer.  
Die CI/CD-Pipeline nutzt normale Filesystem-Pfade — die in Szenario I bereits auf `.out/` umgestellt wurden.

Im CI-Umfeld:
- Output landet in `.out/coverage/backend/` auf dem ephemeren GitHub-Runner-Filesystem
- Das ist korrekt — Coverage wird vor Teardown zu Codecov hochgeladen
- Kein Named Volume in CI

→ **Keine CI/CD-Änderung für Szenario III nötig** (Szenario I hat CI bereits konfiguriert).

---

## Phase 12 — Coverage-Reports einsehen (ohne Host-Filesystem)

Da `.out/` nur im Container existiert, braucht man einen anderen Weg zur Anzeige.

### Option A — Simple Browser in VS Code (empfohlen)

```bash
# Im Container-Terminal nach pytest:
python -m http.server 8080 --directory /workspace/.out/coverage/backend/htmlcov &
```

Dann: VS Code Ports-Panel → Port 8080 öffnen → Coverage-Report im Browser.

### Option B — VS Code Dateizugriff via Remote Explorer

In VS Code Remote Explorer werden Container-Volumes vollständig durchsucht.  
Direkt aus VS Code heraus: Rechtsklick auf `.out/coverage/backend/htmlcov/index.html` → "Open with Live Server" oder "Preview"

### Option C — Coverage Summary im Terminal (kein Browser nötig)

```bash
# pytest gibt Coverage direkt im Terminal aus:
python -m pytest tests/unit --cov=src/opencloudtouch --cov-report=term-missing -x -q
```

---

## Phase 13 — Artefakt-Lebenszyklus verstehen

```
Volume-Lebensdauer:  Solange der Container existiert (inkl. Rebuilds)
Volume-Inhalt:       Überschrieben bei nächstem Test-Run (--cov-report=html überschreibt)
Volume löschen:      docker volume rm oct-artifacts  (oder: docker volume prune)
Effekt nach Löschen: Nächster Container-Start erstellt leeres Volume → postCreateCommand 
                     erstellt Unterordner neu
```

**Konsequenz**: Coverage-History gibt es lokal nicht. Für Trend-Analysen → Codecov.io nutzen.

---

## Phase 14 — Production Build im Container

Der Vite Production Build landet im Volume (nicht auf Host):

```bash
# Im Container:
cd /workspace/apps/frontend
npm run build
# → /workspace/.out/dist/ (im Volume)

# Docker Production Build:
# Findet seinen Build-Context über den Dockerfile (Stage 1: npm build inside Docker)
# Dieser Build ist vom Devcontainer-Volume unabhängig!
```

**Wichtig**: Der `docker build .` für Production-Images läuft außerhalb des Devcontainers
(auf dem Host oder in CI). Er nutzt seinen eigenen internen Build-Kontext und ist dadurch
**nicht abhängig vom Devcontainer-Volume**.

---

## Phase 15 — Validierung

### 15.1 Volume nach Container-Start prüfen

```bash
# Im Container-Terminal:
ls /workspace/.out/
# Erwartet: coverage/ dist/ e2e/ reports/

# Auf dem Host:
ls C:\DEV\private\soundtouch-bridge\.out
# Erwartet: Verzeichnis existiert NICHT oder ist leer
```

### 15.2 Test-Run und Volume-Prüfung

```bash
# Im Container:
cd /workspace/apps/backend
python -m pytest tests/unit --cov=src/opencloudtouch --cov-report=html -x -q

ls /workspace/.out/coverage/backend/htmlcov/
# Erwartet: index.html, coverage_html_*.js, etc.
```

### 15.3 Host ist sauber

```powershell
# Auf dem Host (nicht im Container!):
Get-ChildItem "C:\DEV\private\soundtouch-bridge" -Depth 0 | Select-Object Name
# Erwartet: apps, deployment, docs, scripts, .github, Dockerfile, package.json... 
# KEIN .out/, kein htmlcov, kein .coverage
```

---

## Phase 16 — Commit

```powershell
git add .devcontainer/devcontainer.json

git commit -m "feat(devcontainer): isolate generated artifacts in Docker volume

- Mount named volume oct-artifacts to /workspace/.out
- Generated files (coverage, dist, e2e-logs) never appear on host filesystem
- postCreateCommand creates .out/ subdirectory structure on first run
- Host workspace = pure source code, always clean"
```

---

## Bekannte Trade-offs

| Vorteil | Nachteil |
|---|---|
| Host-Workspace immer sauber | `docker volume prune` löscht alles (erwartet) |
| Keine gitignore-Pflegung für Artefakte nötig | Artefakte nicht direkt mit Windows Explorer zugänglich |
| Isolierung: Artefakte nie versehentlich committed | Ersten-Start-Zeit: Volume wird initialisiert |
| Reports via VS Code Simple Browser zugänglich | Außerhalb Devcontainer: .out/ Pfade funktionieren nicht |

---

## Rollback zu Szenario II

Falls Volume-Isolation stört: Einfach `"mounts"` aus `devcontainer.json` entfernen.  
Dann schreibt pytest/vitest wieder in bind-gemountetes `.out/` auf dem Host.  
→ Volume-Daten gehen verloren (sind ephemer, kein Verlust).

---

## Erfolgskriterien

- [ ] Szenario I + II Kriterien alle erfüllt
- [ ] Nach Container-Start: `/workspace/.out/` im Container hat die 5 Unterordner
- [ ] Nach `python -m pytest --cov`: Artefakte in `/workspace/.out/coverage/backend/` (Container)
- [ ] **Host-Filesystem hat kein `.out/`** (oder nur leeres Verzeichnis)
- [ ] `docker build .` läuft durch (unabhängig vom Devcontainer-Volume)
- [ ] GitHub Actions CI/CD: Unverändert, Coverage wird korrekt zu Codecov hochgeladen
