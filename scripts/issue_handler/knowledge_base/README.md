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

## 2. Antworten aus verifizierten Quellen

Der Issue Handler antwortet einmal, 5 bis 10 Minuten nach einem neuen Issue oder einer neuen Discussion (`answer_delay_*` in `rules.yml`). Er bleibt still, wenn inzwischen ein Mensch oder der Bot geantwortet hat, der Thread geschlossen ist oder `spec`/`needs-human` trägt. Quellen sind ausschließlich `approved_answers/`, README und `docs/` (abschnittsweise) sowie Threads mit dem Label `verified-solution` (`retrieval.py`). Ohne Quelle ab `min_relevance` gibt es keine Antwort. Jede Antwort nennt ihre Quellen und trägt den Marker `<!-- oct-bot:answer -->`.

Betrieb: Standard ist der Trockenlauf (Schreibzugriffe werden nur geloggt). Live schalten: Repository-Variable `OCT_BOT_DRY_RUN` auf `false` setzen. Lokal: `OCT_BOT_DELAY_MIN`/`OCT_BOT_DELAY_MAX` (Sekunden) überschreiben die Wartezeit.

**Nachfrage und Verifikation (Job `follow-up` im Workflow Community, täglich):** Support-Threads (Label `support`/`needs-info` oder mit Bot-Antwort), die ruhig sind, bekommen genau eine Nachfrage: Fall 1 (es gibt Antworten) nach 3 Tagen mit den Kandidaten A bis F, G "etwas anderes", H "nicht gelöst"; Fall 2 (keine Antworten) nach 7 Tagen mit einer offenen Frage und Label `unanswered` nach 3 Tagen; Fall 3 (nur der Ersteller schrieb weiter) bestätigt die genannte Lösung. Antwortet der Ersteller (Buchstabe oder Freitext), schreibt der Bot zurück, was er verstanden hat, und setzt bei "gelöst" das Label `verified-solution` und schließt den Thread (Discussion: Antwort markieren und schließen); bei "nicht gelöst" kommt das Label `needs-human`. Nur Threads mit `verified-solution` werden zur Quelle. Einstellungen: `followup_*` und `unanswered_label_days` in `rules.yml`. Manuell starten: Workflow Community, Haken `follow_up`.

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

## 6. Best Practices

- **Jeder Artikel muss verifiziert und reviewt sein** (keine Halluzinationen)
- **Tags und Titel sauber pflegen** — erleichtert Coverage-Scan und Zuordnung
- **Automatisierte Drafts immer manuell prüfen**
- **Deprecation statt Löschen** — Historie bleibt nachvollziehbar

---

## 7. Troubleshooting

- Workflow läuft nicht? → Logs in GitHub Actions prüfen
- KI-Draft schlägt fehl? → Prompt/Issue-Text prüfen, ggf. manuell nacharbeiten

---

## 8. Weiterführende Links

- [OpenCloudTouch GitHub](https://github.com/opencloudtouch/opencloudtouch)
- [README im Root](../../../README.md)
- [Troubleshooting](../../../docs/TROUBLESHOOTING.md)

---

**Letzte Aktualisierung:** 2026-05-29
