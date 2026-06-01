# Community Spotlight Workflows

Diese Workflows automatisieren die Anerkennung von Community-Mitgliedern.

## 📅 Monthly Community Spotlight (Announcement)

**Datei:** `.github/workflows/monthly-community-spotlight.yml`

### Was macht der Workflow?

Jeden **1. des Monats um 06:00 UTC** automatisch:

1. **Sammelt Aktivitäten** der letzten 30 Tage:
   - Issues erstellt
   - Issue-Kommentare
   - Discussion-Kommentare

2. **Berechnet Scores:**
   - Issues erstellt: 10 Punkte
   - Issue-Kommentare: 2 Punkte
   - Discussion-Kommentare: 1 Punkt

3. **Erstellt GitHub Discussion** in "Announcements" mit:
   - Top 10 Contributors
   - Aktivitäts-Details
   - Link zu BuyMeACoffee

### Manueller Test

```bash
# Im GitHub Repository:
Actions → Monthly Community Spotlight Announcement → Run workflow

# Oder lokal testen (benötigt gh CLI + GitHub Token):
gh workflow run monthly-community-spotlight.yml
```

### Output-Beispiel

```markdown
# 🌟 Community Spotlight — June 2026

Thank you to our most active community members from the past month!

## 🏆 Top Contributors

### @Zimbo88
- **Activity:** 2 issue(s), 14 comment(s)
- **Impact:** Active bug reporting and community support

### @BullHurley
- **Activity:** 2 issue(s), 24 comment(s)  
- **Impact:** Active community support and debugging help

[...]

---

## 💛 Support OpenCloudTouch

☕ [Buy Me a Coffee](https://buymeacoffee.com/b49rjg5k6vj)

Financial supporters are featured in **Settings → About**!
```

---

## 💰 Supporter Sync (kommt später)

**Status:** 🚧 Planned

Automatischer Sync von BuyMeACoffee Supporters via API.

**Voraussetzungen:**
- BMC API Token
- `BMC_API_TOKEN` als GitHub Secret

**Workflow:** `.github/workflows/sync-supporters-bmc.yml`

---

## 🔧 Troubleshooting

### "Discussion not created"

**Ursache:** Keine "Announcements"-Kategorie in GitHub Discussions

**Lösung:**
```bash
# GitHub Repo → Discussions → Categories → Neue Kategorie erstellen
Name: Announcements
Format: Announcement (nur Maintainer können posten)
```

### "Permission denied"

**Ursache:** Workflow hat keine Discussions-Berechtigung

**Lösung:** Bereits konfiguriert in Workflow (`permissions: discussions: write`)

---

## 📊 Anpassungen

### Scoring-Formel ändern

In `.github/workflows/monthly-community-spotlight.yml`, Zeile ~95:

```bash
score: (.issuesCreated * 10) + (.issueComments * 2) + (.discussionComments * 1)
#      ^^^^^^^^^^^^^^^^ HIER anpassen
```

### Top-N ändern (aktuell Top 10)

Zeile ~100:

```bash
.[0:10]
#  ^^^ Anzahl der Top-Contributors
```

### Zeitraum ändern (aktuell 30 Tage)

Zeile ~30:

```bash
SINCE=$(date -d '30 days ago' +'%Y-%m-%d')
#              ^^ Tage
```
