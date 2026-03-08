# Workspace Cleanup — Neue Analyse

> **Rolle**: Principal Workspace Architect, 25+ Jahre, IEEE Best Practices Award 2019  
> **Mandat**: Komplettlösung. Kein Kompromiss. Alle Probleme gleichzeitig adressiert.

---

## Inventar der Probleme

| # | Problem | Auswirkung |
|---|---|---|
| P1 | Docs-Chaos: 5 READMEs + 14 docs/ + kein Index | Orientierungslos |
| P2 | Generierte Artefakte an 6 Orten (`.coverage`, `htmlcov/`, `dist/`, `e2e-*.txt`...) | Workspace = Müllkippe |
| P3 | 3 `.gitignore`-Dateien, 2 vollständig redundant | Falsche Sicherheit |
| P4 | `apps/backend/adapters/` — toter Code, 0 Imports | Verwirrung |
| P5 | Root-Level-Chaos: 23+ Dateien sichtbar | Kein klarer Einstiegspunkt |
| P6 | Kein Devcontainer — jeder Entwickler richtet manuell ein | Onboarding-Pain |
| P7 | `apps/backend/docs/` hat 1 falsch platzierte Datei | Struktur-Lüge |

---

## Szenarien-Analyse

**Bewertet wurden 6 Ansätze:**

1. **Incrementelle Haushaltsführung** — Zu wenig ambitioniert, löst P1/P2 nicht wirklich
2. **Turborepo** — Löst Artefakte via Cache, aber neues großes Tool, overkill für diesen Stack
3. **GitHub Pages + MkDocs** — Schöne Docs-Site, aber CI/CD-Overhead, Docs bleiben im Repo
4. **GitHub Wiki + .out/ (kein Devcontainer)** — Gut, aber Onboarding-Problem bleibt
5. **Devcontainer + Host-.out/** — Clean Dev-Environment, Artefakte noch auf Host sichtbar
6. **Devcontainer + Volume-Isolation** — Maximale Reinheit, Artefakte nie auf Host

→ **Top 3: Szenarien 4, 5, 6**

---

## Top 3 Szenarien

---

### 🥇 Szenario I — "Wiki-First + Zentralisierung"

**Philosophie**: Alle Probleme mit Zero neuen Tools. Nur Umstrukturierung.

**Was passiert**:
- **Docs → GitHub Wiki**: `docs/` vollständig migriert. Repo behält nur `README.md` pro Package (kein dedizierter `docs/`-Ordner mehr). Wiki ist searchable, versioniert durch GitHub
- **Alle Artefakte → `.out/`**: pytest, vitest, vite build, cypress, e2e-logs. Ein Ordner in `.gitignore`. Root und Package-Ordner bleiben nach Testläufen clean
- **Single `.gitignore`**: 3 → 1. Sub-gitignores weg
- **Toter Code**: `adapters/` weg
- **Docker + CI/CD angepasst**: COPY-Pfad im Dockerfile auf `.out/dist` — CI/CD Coverage-Pfade auf neues `.out/`-Schema

**Aufwand**: 5–6h  
**Risiko**: Mittel (Dockerfile + CI/CD Pfadänderungen)  
**Ergebnis**: Root mit ~12 Einträgen statt 23. Workspace nach Build/Test immer sauber.

**Implementierungsdokument**: `docs/IMPL_I_WIKI_CENTRALIZE.md`

---

### 🥈 Szenario II — "Devcontainer + Wiki + .out/"

**Philosophie**: Wie Szenario I, aber Entwicklungsumgebung wird einmal konfiguriert und nie wieder per Hand eingerichtet.

**Was passiert** (alles aus Szenario I, plus):
- **`.devcontainer/devcontainer.json`**: ~25 Zeilen. Basiert auf `mcr.microsoft.com/devcontainers/python:3.13` + Node.js Feature. VS Code erkennt automatisch beim Öffnen.
- **Automatisch verfügbar im Container**: Python 3.13 venv, Node 20, npm, pre-commit installiert und aktiviert, alle VS Code Extensions (Python, Pylance, ESLint, Prettier) vorinstalliert
- **Onboarding**: `git clone` → VS Code öffnen → "Reopen in Container" → fertig. Kein `pip install`, kein `npm install` manuell
- **Artefakte**: Landen in `.out/` — auf Host sichtbar (gitignored), aber sauber

**Aufwand**: 6–7h  
**Risiko**: Mittel (Windows + WSL2 + Devcontainer can be fiddly — aber VS Code Remote Containers ist für diesen Stack Standard)  
**Ergebnis**: Wie Szenario I + jeder neue Entwickler hat in 5 Minuten eine funktionierende Umgebung.

**Implementierungsdokument**: `docs/IMPL_II_DEVCONTAINER.md`

---

### 🥉 Szenario III — "Devcontainer + Wiki + Volume Isolation"

**Philosophie**: Host-Workspace = immer sauber. Eine Datei mehr und du merkst, dass etwas nicht stimmt.

**Was passiert** (alles aus Szenario II, aber anders für Artefakte):
- **Kein `.out/` auf Host** — stattdessen: Named Docker Volume `oct-artifacts` über `devcontainer.json` mount
- Alle Test-Outputs, Coverage-Reports, Builds landen im Container-Volume — **Host sieht nichts davon**
- Zugriff auf Reports: VS Code Simple Browser zeigt `htmlcov/index.html` direkt aus dem Container
- **CI/CD**: Läuft in GitHub Actions (kein Container dort), nutzt weiterhin normale Pfade → CI/CD braucht KEINE Anpassung der Coverage-Pfade (das Volume-Setup ist nur lokal)
- **Docker Production Build**: Unveränderter Dockerfile (baut im eigenen Kontext, Volume-Setup betrifft nur devcontainer)

**Aufwand**: 7–8h  
**Risiko**: Mittel–Hoch (Named Volumes: bei `docker volume prune` weg, nicht sofort intuitiv für neue Entwickler)  
**Ergebnis**: Der sauberste Workspace den es gibt. Host = nur Quellcode.

**Implementierungsdokument**: `docs/IMPL_III_VOLUME_ISOLATION.md`

---

## Entscheidungsmatrix

| Kriterium | Szenario I | Szenario II | Szenario III |
|---|---|---|---|
| Root-Level clean | ✅ | ✅ | ✅ |
| Artefakte weg aus Workspace | ✅ (gitignored) | ✅ (gitignored) | ✅✅ (unsichtbar) |
| Docs in Wiki | ✅ | ✅ | ✅ |
| Onboarding-Erfahrung | 🟡 Manuell | ✅ 1-Click | ✅ 1-Click |
| Host-Workspace Reinheit | 🟡 sauber nach commit | 🟡 sauber nach commit | ✅ immer sauber |
| Neue Tools einführen | Keine | Devcontainer | Devcontainer + Volume |
| CI/CD Anpassungen | Ja (Pfade) | Ja (Pfade) | Minimal (Pfade nur lokal) |
| Dockerfile Anpassungen | Ja | Ja | Nein |
| Risiko | Mittel | Mittel | Mittel-Hoch |
| Aufwand | 5–6h | 6–7h | 7–8h |
