# Implementierungsdokument II — "Devcontainer + Wiki + .out/"

> **Voraussetzungen**: VS Code + Extension "Dev Containers" (ms-vscode-remote.remote-containers)  
> **Zeit**: 6–7 Stunden (inklusive Szenario I)  
> **Ergebnis**: Szenario I komplett + 1-Click-Onboarding für jeden Entwickler

---

## Was Szenario II zusätzlich zu Szenario I bringt

Szenario II = Szenario I vollständig umgesetzt + `.devcontainer/` Setup.  
Alle Phasen 1–5 aus `IMPL_I_WIKI_CENTRALIZE.md` zuerst ausführen, dann hier weitermachen.

---

## Phase 6 — Devcontainer einrichten (1–2h)

### 6.1 Was der Devcontainer löst

Aktuell muss ein neuer Entwickler manuell einrichten:
- Python 3.13 + venv
- `pip install -r requirements-dev.txt`
- `npm install` in root und `apps/frontend/`
- `.env` aus `.env.template` erstellen
- `pre-commit install`
- VS Code Extensions (Python, Pylance, ESLint, Prettier, Ruff)

Mit Devcontainer: `git clone` → VS Code öffnen → **"Reopen in Container"** → Fertig.

### 6.2 `.devcontainer/devcontainer.json` erstellen

```powershell
New-Item -ItemType Directory -Force "C:\DEV\private\soundtouch-bridge\.devcontainer"
```

Datei `.devcontainer/devcontainer.json`:

```json
{
  "name": "OpenCloudTouch Dev",
  "image": "mcr.microsoft.com/devcontainers/python:1-3.13-bookworm",

  "features": {
    "ghcr.io/devcontainers/features/node:1": {
      "version": "20"
    }
  },

  "postCreateCommand": "pip install -r apps/backend/requirements-dev.txt && npm ci && npm ci --prefix apps/frontend && pre-commit install",

  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.pylance",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "esbenp.prettier-vscode",
        "dbaeumer.vscode-eslint",
        "vitest.explorer",
        "ms-vscode.test-adapter-converter"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "esbenp.prettier-vscode",
        "[python]": {
          "editor.defaultFormatter": "charliermarsh.ruff"
        }
      }
    }
  },

  "forwardPorts": [7777, 5173],
  "portsAttributes": {
    "7777": { "label": "Backend API" },
    "5173": { "label": "Frontend Dev Server" }
  }
}
```

### 6.3 `.devcontainer/` zu `.gitignore` prüfen

`.devcontainer/` soll NICHT in `.gitignore` — es soll ins Git!  
Prüfen dass es nicht versehentlich ignoriert wird:

```powershell
git check-ignore -v ".devcontainer/devcontainer.json"
# Erwartet: KEIN Output (= nicht ignoriert)
```

### 6.4 Optional: `devcontainer.json` mit `docker-compose` verbinden

Falls du den Stack lokal mit docker-compose läufst, kann der Devcontainer
denselben Compose-Stack nutzen:

```json
// Erweiterung in devcontainer.json (optional):
"dockerComposeFile": "../deployment/docker-compose.yml",
"service": "backend",
"workspaceFolder": "/workspace"
```

> Nur sinnvoll wenn du die komplette `docker-compose`-Infrastruktur im Dev nutzen willst.
> Für normales Entwickeln reicht das einfachere Szenario aus Schritt 6.2.

### 6.5 `postStartCommand` für häufige Checks (optional)

```json
"postStartCommand": "git config --global --add safe.directory ${containerWorkspaceFolder}"
```

Verhindert git-Warnings bei Windows-gemounteten Volumes.

---

## Phase 7 — Windows-spezifische Devcontainer Optimierungen

### 7.1 Performance: Workspace in Container-Volume speichern

Für bessere I/O-Performance unter Windows (WSL2-Filesystem vs. bind-mount):

```json
// In devcontainer.json ergänzen:
"workspaceMount": "source=oct-workspace,target=/workspace,type=volume",
"workspaceFolder": "/workspace"
```

> **Achtung**: Bei `workspaceMount` als Volume muss der Code vom Volume aus versioniert werden.
> VS Code erstellt das Volume automatisch und klont den Code hinein.
> Für das erste Setup dauert es etwas länger — danach extrem schnell.

### 7.2 `.wslconfig` empfehlen (in `.devcontainer/README.md`)

```markdown
## Windows-Setup

Für beste Performance mit WSL2:

Datei `%USERPROFILE%\.wslconfig` erstellen:
\`\`\`
[wsl2]
memory=6GB
processors=4
\`\`\`
```

---

## Phase 8 — Validierung Devcontainer

### 8.1 Container erstellen

```
VS Code: F1 → "Dev Containers: Rebuild and Reopen in Container"
```

Erwartet: Container build läuft (~3-5 Minuten beim ersten Mal), dann VS Code öffnet sich im Container.

### 8.2 Umgebung prüfen

Im Container-Terminal:
```bash
python --version     # Muss: Python 3.13.x
node --version       # Muss: v20.x.x
npm --version        # Muss: 10.x.x
pre-commit --version # Muss: pre-commit x.x.x
```

### 8.3 Tests im Container laufen lassen

```bash
# Im Container-Terminal:
cd /workspace
python -m pytest apps/backend/tests/unit -x -q
# Artefakte: /workspace/.out/coverage/backend/

cd apps/frontend
npm run test:unit
# Artefakte: /workspace/.out/coverage/frontend/
```

### 8.4 Port-Forwarding prüfen

```bash
# Backend starten:
cd /workspace
python -m uvicorn opencloudtouch.main:app --reload --port 7777
```

In VS Code: Ports-Panel sollte automatisch Port 7777 forwarden.
Browser: `http://localhost:7777/docs` zeigt FastAPI Swagger.

---

## Phase 9 — Commit

```powershell
# Im Host-Terminal (nicht im Container):
git add .devcontainer/
git add .devcontainer/README.md 2>$null

git commit -m "feat(devcontainer): add VS Code Dev Container configuration

- Python 3.13 + Node 20 base image
- postCreateCommand: pip install + npm ci + pre-commit install
- VS Code extensions: Python, Pylance, Ruff, Prettier, ESLint, Vitest
- Port forwarding: 7777 (Backend API), 5173 (Frontend Dev Server)
- Onboarding: git clone → Reopen in Container → done"
```

---

## Erfolgskriterien (zusätzlich zu Szenario I)

- [ ] `.devcontainer/devcontainer.json` im git-tracked
- [ ] "Reopen in Container" in VS Code öffnet Container ohne Fehler
- [ ] `python --version` im Container-Terminal = 3.13.x
- [ ] `node --version` im Container-Terminal = 20.x
- [ ] `pre-commit --version` = vorhanden
- [ ] VS Code Extensions automatisch installiert (Python, Ruff, ESLint, Prettier)
- [ ] Port 7777 wird automatisch geforwarded
- [ ] Backend und Frontend Tests laufen im Container durch
- [ ] `.out/` Artefakte landen im Container (via bind-mount sichtbar auf Host)
