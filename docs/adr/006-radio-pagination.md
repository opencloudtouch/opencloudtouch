# ADR-006: Radio Search Pagination ("Mehr laden")

**Status:** Proposed  
**Issue:** [#93 — RadioBrowser results differ from website results](https://github.com/scheilch/opencloudtouch/issues/93)  
**Branch:** `feat/radio-pagination`  
**Date:** 2026-04-22

## Problem

Die RadioBrowser-Suche nach Land (z.B. "Luxembourg") liefert ~30 Sender, aber OpenCloudTouch zeigt nur die ersten 10 (alphabetisch sortiert). RTL-Sender starten ab Position ~22 und werden nie angezeigt. Die RadioBrowser-Website zeigt alle Sender.

**Ursache:** `limit=10`, kein `offset`-Parameter, keine Pagination.

## Entscheidung

**"Mehr laden"-Button** mit `offset`-basierter Pagination.

```
┌─────────────────────────────────────┐
│ 🔍 Luxembourg                   ✕  │
│ [Name] [Land] [Genre]              │
│ [RadioBrowser] [TuneIn]            │
├─────────────────────────────────────┤
│ 📻 AAAudio                         │
│    Luxembourg                       │
│ 📻 Braintrip Radio                 │
│    Luxembourg                       │
│ ... (10 Ergebnisse)                 │
├─────────────────────────────────────┤
│         [+ Mehr Sender laden]       │  ← NEU
└─────────────────────────────────────┘
```

Erneutes Klicken lädt die nächsten 10 (offset=10, 20, ...) und hängt sie an. Button verschwindet wenn < 10 Ergebnisse zurückkommen (= letzte Seite).

## Änderungsplan

### Phase 1: Backend — `offset` Parameter

**Datei:** `apps/backend/src/opencloudtouch/radio/api/routes.py`
- `offset` Query-Parameter hinzufügen (int, default=0, ge=0)
- An Adapter-Methoden durchreichen

**Datei:** `apps/backend/src/opencloudtouch/radio/provider.py`
- Interface `search_by_name`, `search_by_country`, `search_by_tag`: Parameter `offset: int = 0` hinzufügen

**Datei:** `apps/backend/src/opencloudtouch/radio/providers/radiobrowser.py`
- `offset` an RadioBrowser API als Query-Param übergeben (nativ unterstützt)
- Optional: `hidebroken=true` und `order=votes&reverse=true` als Defaults setzen

**Datei:** `apps/backend/src/opencloudtouch/radio/providers/tunein.py`
- TuneIn hat keine native Pagination → `offset` client-seitig mit Slicing: `stations[offset:offset+limit]`

**Datei:** `apps/backend/src/opencloudtouch/radio/providers/mock.py`
- `offset` mit Slicing: `results[offset:offset+limit]`

**Datei:** `apps/backend/openapi.yaml`
- `offset` Parameter dokumentieren

### Phase 2: Frontend — "Mehr laden" Button

**Datei:** `apps/frontend/src/components/RadioSearch.tsx`

State-Änderungen:
```typescript
const [offset, setOffset] = useState(0);
const [hasMore, setHasMore] = useState(false);
const [loadingMore, setLoadingMore] = useState(false);
```

Logik:
- `handleSearch()`: Bei neuer Suche → `offset=0`, `results=[]`
- `handleLoadMore()`: `offset += 10`, Ergebnisse appenden (nicht ersetzen)
- `hasMore`: `true` wenn genau `limit` (10) Ergebnisse zurückkommen
- Suchtyp/Provider-Wechsel → Reset offset & results

API-Call anpassen:
```typescript
`${baseUrl}/api/radio/search?q=${query}&search_type=${searchType}&limit=10&offset=${offset}&provider=${provider}`
```

**Datei:** `apps/frontend/src/components/RadioSearch.css`

Neue Klassen:
```css
.search-load-more { /* Button-Styling, full-width, zentriert */ }
.search-load-more:disabled { /* Loading-State */ }
```

### Phase 3: Tests

**Backend-Tests (TDD — Test zuerst):**

| Testdatei | Testfälle |
|-----------|-----------|
| `tests/unit/radio/api/test_radio_routes.py` | offset=0 default, offset=10 passed, offset<0 → 422, offset+limit Kombination |
| `tests/unit/radio/providers/test_radiobrowser.py` | offset an API übergeben, hidebroken default |
| `tests/unit/radio/providers/test_tunein.py` | offset client-seitig slicing |
| `tests/unit/radio/providers/test_mock.py` | offset slicing korrekt |

**Frontend-Tests:**

| Testdatei | Testfälle |
|-----------|-----------|
| `tests/unit/RadioSearch.test.tsx` | "Mehr laden" Button sichtbar bei 10 Ergebnissen, unsichtbar bei <10, Ergebnisse werden appended, offset reset bei neuer Suche |
| `tests/e2e/radio-search-robustness.cy.ts` | Pagination E2E (Mock-Mode) |

### Phase 4: Optional — Bessere Defaults

Unabhängig von Pagination, als separate Commits:
- `hidebroken=true` standardmäßig setzen (keine kaputten Sender anzeigen)
- `order=votes&reverse=true` als Default (populärste zuerst statt alphabetisch)

Dies würde das Issue #93 auch ohne Pagination stark verbessern, da die RTL-Sender (2270 Votes) vor AAAudio (1 Vote) erscheinen würden.

## Betroffene Dateien (Übersicht)

| Datei | Änderung |
|-------|----------|
| `apps/backend/src/opencloudtouch/radio/api/routes.py` | `offset` Parameter |
| `apps/backend/src/opencloudtouch/radio/provider.py` | Interface erweitern |
| `apps/backend/src/opencloudtouch/radio/providers/radiobrowser.py` | `offset` + optional `hidebroken`/`order` |
| `apps/backend/src/opencloudtouch/radio/providers/tunein.py` | Client-seitiges Offset-Slicing |
| `apps/backend/src/opencloudtouch/radio/providers/mock.py` | Offset-Slicing |
| `apps/backend/openapi.yaml` | Doku |
| `apps/frontend/src/components/RadioSearch.tsx` | Pagination-State + "Mehr laden" Button |
| `apps/frontend/src/components/RadioSearch.css` | Button-Styling |
| Tests (6+ Dateien) | Neue Testfälle |

## Nicht im Scope

- Kombinations-Suche (Land + Name gleichzeitig) → Separates Feature
- Infinite Scroll → Zu komplex für den Mehrwert
- Server-seitige Sortier-Optionen im UI → Separates Feature

## Risiken

- **TuneIn:** Hat keine native Pagination — bei vielen Ergebnissen wird die volle Liste geholt und client-seitig gesliced. Akzeptabel, da TuneIn ohnehin weniger Sender liefert.
- **RadioBrowser API:** `offset` + `limit` sind nativ unterstützt, kein Risiko.
