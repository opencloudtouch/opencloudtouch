# Refactoring-Status
Letzte Aktualisierung: 2026-05-10 02:45

## Aktuelle Phase
Abgeschlossen — Tests grün, bereit zum Commit

## Abgeschlossen
- [x] R-001: Frontend API throwIfNotOk() — 8 API-Dateien, 45→0 Duplikate, 657/657 Tests grün
- [x] R-002: Backend Exception Handler Factory — 5 Handler durch Factory ersetzt, ~60 Zeilen eingespart
- [x] R-003: Backend f-string → lazy logging — 160+ Stellen konvertiert, 0 verbleibend, 1255/1255 Tests grün

## Offen
(keine)

## Geparkt (Aufwand > Nutzen)
- R-004: main.py lifespan aufteilen — funktioniert, Aufwand L
- R-005: usePolling() Hook extrahieren — für späteren Sprint
