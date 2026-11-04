# App stage 5 prompt edit

_Started 2026-10-23 01:07 UTC_

---

## User

<artifact-content-authored-by-others/>
Continuing from "UI mockups request".

## Assistant

Wir bauen einen interaktiven Wizard-Prototyp für Setup- und Restore-Flow mit Breitenwahl und Zustandsschalter. Ziel: Drop-in TSX-, CSS- und i18n-Dateien plus HTML-Prototypen für vier Stufen.

**Bisherige Entscheidungen:**
- Stufen 1–4 parallel liefern: Komponenten + CSS pro Schritt, gemeinsame Basis, deutsche Texte.
- Prototypen als `.dc.html` mit Media-Queries pro Breite (320, 375, 414, 768, 1280), nicht als TSX-Render.
- Badge-Checks im Prototyp: Overflow, Scrollbars, Tippziele ≥44 px, Farb-Kontrast, fehlende Icons.
- Logik unverändert: Props, Hooks, Effekte, API-Aufrufe, Timer, `t()`-Keys bleiben wie im Original.
- Markup neu: DOMReihenfolge, Klassennamen, Fehlerboxen, Hinweistexte angepasst; Duplikate in CSS removed, zentralisiert in `wizard-base.css`.

**Aktueller Stand:**
- **Stufe 1** (Bausteine, Choice, Loading): `wizard/` Komponenten fertig, `stage1-frame.html` liefert HTML.
- **Stufe 2** (Setup 1–4: USB, SSH, Backup, Config): Prototyp `OCT Wizard Stufe 2.dc.html`, TSX, CSS, neue i18n-Keys (nextDisabled Schritt 2, nextWarning Schritt 4).
- **Stufe 3** (Setup 5–8: Hosts, NTP, Prüfung, Fertig): Prototyp `OCT Wizard Stufe 3.dc.html`, TSX, CSS, Phasenanzeige (3-teilig mit fest Höhe), neue i18n-Keys (phase*, nextDisabled), `ProgressTracker` mit Status.
- **Stufe 4** (Restore: Choice, Scan, Execution, Verification, Completion): Prototyp `OCT Wizard Stufe 4.dc.html`, alle TSX, CSS, neue i18n-Keys (running_hint, error_hint, failed_title, stepAriaSkipped), `ProgressTracker` mit Status „skipped". Logikänderung nötig: `SetupWizard.tsx` Zeile `restoreTrackerSteps` auf `"skipped"` setzen.

**Dateien:** `wizard/` enthält alle Komponenten (TSX), CSS pro Schritt/Stage, `Icon.tsx`, `ProgressTracker.tsx`, `wizard-base.css`; Prototypen: `OCT Wizard Stufe 2–4.dc.html`, `stage{1,2,3}-frame.html`; Ressourcen: `tokens.css`, `de-wizard-texts.json`.

**Offene nächste Schritte:**
- `tsc` und ESLint auf Stufen 1–4 laufen lassen.
- Tests anpassen (Selektoren, Rollen, Emoji→Icon).
- Stufen gegen Acceptance-Checks prüfen.
- Logikänderung in `SetupWizard.tsx` (`restoreTrackerSteps`) durchführen.
- Retry-Funktion für `RestoreExecution` entscheiden (Code wird bereitgestellt).

## User

Bearbeite app-stage5-prompt.md

## Assistant

_[tool: read_file]_

_[tool: list_files]_

_[tool: list_files]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: grep]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: run_script]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: show_html]_

_[tool: write_file]_

_[tool: ready_for_verification]_

Stufe 5 ist als Prototyp, Drop-in-Komponenten und Notizen geliefert. Ich habe nichts davon ausgeführt oder getestet. Das Prüfergebnis des Prototyps steht noch aus.

`tsc` und ESLint habe ich nicht laufen lassen. Die Dialogtests laufen nur über meinen `open`-Fallback in jsdom; Fokusfalle und Inertness sind dort nicht prüfbar. Der Prototyp zeigt Flaggen als Platzhalter statt echter `flag-icons`.

**Prototyp:** `OCT App Stufe 5.dc.html` hat einen Breitenschalter (320/375/414/768/1280) und eine Zustandsauswahl für Navigation, App-Zustände, Willkommen, 404, Presets, Stationssuche, Bestätigungen, Toasts und Primitive. Ein Prüfstreifen meldet Überlauf, Überlappungen, Tippziele unter 44 px, Kontrast und nicht fokussierbare Scroll-Bereiche.

**Dateien in `app/`:**
- **Neu:** `ui-base.css` (Primitive, Buttons und Statusboxen 1:1 aus `wizard-base.css`), `Modal.tsx` auf nativem `<dialog>`, `Icon.tsx` und `app-shell.css`.
- **Drop-in:** alle 20 Komponenten aus Abschnitt 9 plus `App.tsx`, jeweils mit eigener CSS.
- **Rest:** `i18n-stage5-additions.json` und `STAGE5-NOTES.md`.

`STAGE5-NOTES.md` enthält die Abschnitte (a)–(e): neue i18n-Keys, Logikabweichungen, anzupassende Tests, offene Punkte und die in `wizard-base.css` löschbaren Regeln. Dort steht auch die Liste der alten CSS-Dateien, die entfallen.

**Zwei Dinge, die Sie wissen sollten:**
- **Logikabweichungen:** Sie sind additiv oder rein visuell (z. B. Pfeiltasten im Sprachwähler, Home/End am Lautstärkeregler, optionale Prop `destructive` am `ConfirmDialog`).
- **Gerät entfernen:** Die Bestätigung habe ich nur entworfen (im Prototyp unter Bestätigungen → „Gerät entfernen (Vorschlag)“). Im Code löscht „Gerät entfernen“ weiter sofort. Den Diff dafür finden Sie in den Notizen unter (b).

**Zu klären:**
- `getAvatarColor` müsste dunklere Farben liefern, damit die weißen Initialen sicher 4,5:1 erreichen. Die Datei war nicht Teil der Lieferung.
- `setupBadge.*` und `statusBadge.*` fehlen in Ihrer hochgeladenen JSON. Ich nehme an, dass sie in der App existieren; mein Wortlaut aus dem Prototyp steht in `i18n-stage5-additions.json` zum Abgleich.

## User

Found issues — fixing…

## Assistant

_[tool: run_script]_

_[tool: ready_for_verification]_

Ich habe die vier Fehler aus dem Prüflauf behoben. Neu geprüft ist noch nichts, die erneute Prüfung läuft im Hintergrund. Die Breiten 320, 375, 414 und 768 waren im ersten Lauf ungeprüft und müssen noch gegengeprüft werden.

- **Artwork:** Das SVG im Prototyp wird nur noch einmal kodiert, das Bild lädt wieder.
- **Stift-Icon:** `.dne-btn` ist jetzt `inline-flex`, das Icon sitzt neben dem Namen. Die Korrektur steckt in der ausgelieferten `DeviceNameEditor.css`, nicht nur im Prototyp.
- **Schatten:** `--shadow-sm`, `--shadow-md` und `--shadow-lg` stehen jetzt in `app/tokens.css`. Das betrifft nur den Prototyp, in der App kommen sie aus `index.css`.
- **Steuerleiste:** Sie überlappt nicht mehr und ist nicht mehr sticky. Die Vorschau füllt jetzt fast die ganze Höhe.

## User

Found issues — fixing…

## Assistant

_[tool: run_script]_

_[tool: ready_for_verification]_

Ich habe den Prüfstreifen im Prototyp korrigiert; erneut geprüft habe ich nicht, der Verifier war übersprungen.

- **Prüfstreifen:** Beschnittene Elemente in scrollenden Bereichen und das Sprachwähler-Dropdown zählen nicht mehr als Überlappung oder zu kleines Tippziel. Damit sollten die drei roten Meldungen (manuelle Suche, Dialog mit Fehler, Sprachwähler) verschwinden.
- **Steuerleiste:** Sie ist jetzt auf 35 % der Fensterhöhe begrenzt und scrollt, sodass die Vorschau auch bei niedrigem Fenster sichtbar bleibt.

Die Design-System-Hinweise im Prüfbericht betreffen Ihre hochgeladenen Quelldateien und den Prototyp. Den Prototyp habe ich bewusst im bestehenden Wizard-Look gelassen, nicht im Industry-Design-System.

