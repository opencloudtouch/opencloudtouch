# Refactoring-Analyse — OpenCloudTouch
Datum: 2026-05-10

## Zusammenfassung
Solide Architektur (Clean Architecture Layers), aber systematische Duplikation in zwei Bereichen:
45x identisches Error-Handling im Frontend API Layer, 6x identische Exception-Handler im Backend.
Einzelne Dateien >400 Zeilen. Mehrere f-string Logging-Stellen (SonarCloud-relevant).

## Funde

### [R-001] Frontend API: 45x dupliziertes Error-Handling
- **Kategorie:** Duplikation
- **Dateien:** devices.ts, presets.ts, zones.ts, setup.ts, wizard.ts, settings.ts, bugReport.ts
- **Aufwand:** M
- **Wirkung:** Hoch
- **Beschreibung:** `if (!response.ok) { ... throw new Error(...) }` in 45 Stellen mit 3 leicht verschiedenen Varianten. Extraktion einer `throwIfNotOk(response, context)` Utility eliminiert alle.

### [R-002] Backend Exception Handlers: Factory-Pattern statt 6x Boilerplate
- **Kategorie:** Duplikation
- **Dateien:** core/exception_handlers.py
- **Aufwand:** S
- **Wirkung:** Mittel
- **Beschreibung:** 6 Handler folgen identischem Muster: log + JSONResponse(ErrorDetail). Factory-Funktion reduziert 80 Zeilen auf ~20.

### [R-003] Backend f-string Logging (SonarCloud Vulnerability)
- **Kategorie:** Security/Convention
- **Dateien:** core/exception_handlers.py (5x), diverse
- **Aufwand:** S
- **Wirkung:** Hoch (SonarCloud blockt sonst)
- **Beschreibung:** `logger.warning(f"Device not found: {exc.device_id}")` → lazy logging

### [R-004] main.py: 93-Zeilen lifespan + 57 Imports
- **Kategorie:** Komplexität
- **Dateien:** main.py (254 Zeilen)
- **Aufwand:** L
- **Wirkung:** Mittel
- **Beschreibung:** Monolithische Startup-Logik. Aufwand > Nutzen für diesen Sprint.

### [R-005] Frontend: Fehlende usePolling()-Abstraktion
- **Kategorie:** Duplikation
- **Dateien:** useNowPlaying.ts, useVolume.ts, useZones.ts
- **Aufwand:** M
- **Wirkung:** Mittel
- **Beschreibung:** 3 Hooks mit identischem setInterval/cleanup Pattern. Für späteren Sprint.

## Empfohlene Reihenfolge
1. R-001 — Quick Win, 45 Duplikate eliminiert
2. R-002+R-003 — Quick Win, Exception Handler Cleanup + f-string Fix
3. R-004, R-005 — Geparkt (Aufwand > Nutzen aktuell)
