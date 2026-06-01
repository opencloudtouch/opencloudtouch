# OpenCloudTouch Knowledge Base (KB) — Maintenance & Growth Workflow

## Overview
This directory contains the curated Knowledge Base (KB) articles, scripts, and automation for the OpenCloudTouch support bot and community intelligence pipeline.

---

## 1. KB-Artikel — Struktur & Pflege

- **Ablageort:** `approved_answers/` — Nur geprüfte, freigegebene Artikel (Markdown mit YAML Frontmatter)
- **Drafts:** `.local/agent-work/knowledge-kai/drafts/` — Neue Artikelentwürfe, noch nicht freigegeben
- **Tags:** Jeder Artikel muss relevante `tags:` im Frontmatter haben (z.B. `docker`, `preset`, `discovery`)
- **Titel:** Menschlich lesbar, im Frontmatter und als Markdown-Heading

### Artikel-Lifecycle
1. **Draft-Generierung:**
   - Manuell (User, Maintainer) oder automatisiert (KI aus Issue/Discussion)
   - Draft landet in `.local/agent-work/knowledge-kai/drafts/`
2. **Review:**
   - User/Maintainer prüft Inhalt, ergänzt/fixiert, setzt Status auf `review`
3. **Freigabe:**
   - Nach Review → Artikel nach `approved_answers/` verschieben, Status auf `approved`
4. **Deprecation:**
   - Veraltete Artikel → Status `deprecated`, im Zweifel nicht löschen

---

## 2. Automatisierte KB-Wachstum & Qualitätskontrolle

### Scheduled Workflow: `.github/workflows/kb-growth.yml`
- Läuft wöchentlich (oder manuell via GitHub Actions)
- Steps:
  1. **KB Growth Scan:**
     - Script: `knowledge_base/kb_growth.py`
     - Scannt geschlossene Support-Issues der letzten Woche
     - Prüft, ob Thema bereits durch KB abgedeckt ist (Tag-Match)
     - Markiert gescannte Issues mit Label `kb-scanned`
     - Erstellt Digest-Report (Markdown)
  2. **Pattern & Quality Scan:**
     - Script: `knowledge_base/pattern_quality_scan.py`
     - Scannt offene Issues/Discussions nach:
       - Frage-/Problem-Patterns ("how", "doesn't work", "fixed", ...)
       - Stale-Threads (>7d ohne Aktivität)
       - KB-Coverage (Tag-Mapping)
       - Response-Quality (Feedback-Signale)
     - Output: YAML-Reports in `.local/agent-work/knowledge-kai/scans/`

---

## 3. KB-Artikel erstellen (manuell)

1. **Neues Markdown-File in `approved_answers/` anlegen**
2. YAML Frontmatter mit `tags:` und `title:` ergänzen
3. Problem/Symptome/Solution/See Also strukturieren
4. PR/Merge → Artikel ist für Bot & Workflow verfügbar

---

## 4. KB-Artikel aus Issues/Discussions generieren (KI-gestützt)

- Script: `knowledge_base/generate_kb_article.py`
- Nutzt OpenAI/Claude, um aus Issue+Comments einen Draft zu erzeugen
- Draft landet in `.local/agent-work/knowledge-kai/drafts/`
- Review & Freigabe wie oben

---

## 5. Reports & Qualitätsmetriken

- Digest-Reports (Markdown): Übersicht neue/abgedeckte Themen
- Pattern/Coverage/Quality-Reports (YAML):
  - `.local/agent-work/knowledge-kai/scans/pattern_quality_threads.yaml`
  - `.local/agent-work/knowledge-kai/scans/pattern_quality_coverage.yaml`
  - `.local/agent-work/knowledge-kai/scans/pattern_quality_quality.yaml`
- Reports dienen als Grundlage für KB-Erweiterung und Bot-Verbesserung

---

## 6. Best Practices

- **Jeder Artikel muss verifiziert und reviewt sein** (keine Halluzinationen)
- **Tags und Titel sauber pflegen** — erleichtert Coverage-Scan und Zuordnung
- **Automatisierte Drafts immer manuell prüfen**
- **Deprecation statt Löschen** — Historie bleibt nachvollziehbar

---

## 7. Troubleshooting

- Workflow läuft nicht? → Logs in GitHub Actions prüfen
- YAML-Reports fehlen? → Rechte/Verzeichnisse prüfen (`.local/agent-work/knowledge-kai/scans/`)
- KI-Draft schlägt fehl? → Prompt/Issue-Text prüfen, ggf. manuell nacharbeiten

---

## 8. Weiterführende Links

- [OpenCloudTouch GitHub](https://github.com/opencloudtouch/opencloudtouch)
- [README im Root](../../../../README.md)
- [FAQ](../../../doc/FAQ.md)

---

**Letzte Aktualisierung:** 2026-05-29
