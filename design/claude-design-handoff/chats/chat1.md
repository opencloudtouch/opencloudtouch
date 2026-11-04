# UI mockups request

_Started 2026-10-20 16:31 UTC_

---

## User

Make UI mockups for

## Assistant



## Assistant

_[tool: read_file]_

_[tool: list_files]_

_[tool: ask_user]_

I've sent you a short form. I'm waiting on your answers about the style conflict, first-round scope, viewports, deliverable and icons. I'll build once they arrive.

## User

<artifact-content-authored-by-others/>
Answered — Asked for follow-up questions; style: Brief only: dark tokens, rounded as specified, no Industry; scope: Shared building blocks sheet (frame, header, tracker, status boxes, buttons, cards, fields), Choice, loading, no-devices, Setup steps 1-4, Setup steps 5-8, Restore steps 1-5; widths: 320, 375, 768, 1280; deliver: Mockups plus wizard-base.css and TSX for finished screens; icons: Lucide-style line icons

## Assistant



## Assistant

_[tool: read_file]_

_[tool: ask_user]_

I've added a second round to the form. I need your answers on mockup format, build order, state coverage, TSX/CSS delivery and copy language. You can also attach existing source files. I'll start building once you submit.

## User

<artifact-content-authored-by-others/>
Answered — format: Interactive wizard prototype with a width switcher and state picker; stages: Stage 1: building blocks + choice/loading/empty. Then setup 1-4, 5-8, restore.; states: All states in the brief (error, loading, success, disabled Next) per step; tsx: Write TSX/CSS per stage alongside mockups, from the brief; lang: German (risk classes suggest German source)

## User

Found issues — fixing…

## User

<artifact-content-authored-by-others/>
Found issues — fixing…

## Assistant

_[tool: run_script]_

_[tool: delete_file]_

I replaced the broken `stage1.tsx` with six separate files in `wizard/`. They are `Icon.tsx`, `DeviceInfoHeader.tsx`, `ProgressTracker.tsx`, `WizardStep.tsx`, `WizardChoice.tsx` and `SetupWizardStates.tsx`. Each is a full component with the original hooks, props and handlers from your uploaded sources, so you can paste them in. I haven't compiled them against your repo.

`SetupWizardStates.tsx` holds the loading and no-devices branch from `SetupWizard.tsx`. `Icon.tsx` contains the inline Lucide icons.

Next up is setup steps 1–4. Tell me if you'd like something else first.

## User

Bearbeite die Datei. Und Kommuniziere auf deutsch - IMMER!

## Assistant

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: grep]_

_[tool: grep]_

_[tool: read_file]_

_[tool: read_file]_

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

_[tool: dc_write]_

_[tool: ready_for_verification]_

Stufe 2 liegt zur Prüfung vor: die vier Schritte USB, Neustart/SSH, Backup und Verbindung als Prototyp mit Breitenwahl und Zustandswahl. Kompiliert oder mit `tsc` und ESLint geprüft habe ich nichts, das müsst ihr bei euch laufen lassen.

**Prototyp** (`OCT Wizard Stufe 2.dc.html`)
- Er hat Breiten 320, 375, 414, 768 und 1280 sowie einen Zustandswähler pro Schritt, mit den echten deutschen Texten aus der JSON.
- Der Prototyp läuft im iframe, damit die Media-Queries pro Breite greifen. Die Vorschau (`wizard/stage2-frame.html`) rendert HTML, das die TSX-Komponenten 1:1 spiegelt, nicht die TSX selbst.
- Ein Badge prüft automatisch horizontalen Overflow und Tippziele unter 44 px.

**Drop-in-Dateien** in `wizard/`
- Komponenten: `Step2USBPreparation.tsx`, `Step3PowerCycle.tsx`, `Step4Backup.tsx` und `Step5ConfigModification.tsx`. Logik, Props, API-Aufrufe, der 30-s-Timer und die i18n-Keys sind unverändert.
- `Icon.tsx` enthält jetzt `LockOpen` für dauerhaftes SSH und `DoorOpen` für vorübergehendes SSH. `CopyableCommand.tsx` zeigt den Kopier-Button jetzt dauerhaft statt nur beim Hover.
- Schritt-CSS: je eine Datei pro Schritt, importiert zusammen mit `wizard-base.css`. Die Duplikate `.error-icon`, `.success-*` und die Spinner liegen jetzt einmal in der Basis.

**Backup nach Fehler:** Weiter bleibt aktiv, wie im Original. Zusätzlich gibt es eine große Fehlerbox und einen Warnhinweis direkt über der Aktionsleiste. Der Weiter-Button wird per `:has(.backup-error)` rot umrandet.

**Auffälligkeiten im Original**
- Bei `result.success === false` ist `backupData` gesetzt, der Button „Backup jetzt erstellen“ verschwindet und ein Wiederholen ist nicht möglich. Das habe ich unverändert gelassen und als Zustand „Fehler (success=false)“ im Prototyp abgebildet.
- Der Hinweistext `successHint` steht im Erfolgszustand zweimal auf der Seite, als Absatz und in der USB-Box. Ich habe ihn nicht entfernt.
- `createFileDesc` enthält `<0>`/`<1>`-Tags, aber der Code ruft nur `t()` auf. Der Prototyp wandelt sie in `code` und `strong` um. Im echten Code erscheinen sie roh, solange kein `Trans` im Einsatz ist.

**Neue i18n-Keys**
- `setup.wizard.step3.nextDisabled`:
  - DE: „Bitte SSH-Zugang prüfen und eine Entscheidung zur SSH-Dauerhaftigkeit treffen.“
  - EN: „Please check SSH access and decide whether SSH stays enabled.“
  - Zu Schritt 2: Er hatte bisher keinen Hinweis bei deaktiviertem Weiter. Das ist nur Text, die Logik bleibt gleich.
- `setup.wizard.step4.nextWarning`:
  - DE: „Ohne Backup ist keine Wiederherstellung möglich. Wenn Sie jetzt fortfahren, geschieht das auf eigenes Risiko.“
  - EN: „Without a backup, restoring is not possible. If you continue now, you do so at your own risk.“
- `setup.trackerCompact` aus Stufe 1 bleibt bestehen.

Als Nächstes kommen Stufe 3 (Schritte 5–8) und Stufe 4 (Restore), wenn ihr Stufe 2 freigebt.

## User

Bearbeite wizard-stage2-prompt.md

## Assistant

_[tool: read_file]_

Die Datei `wizard-stage2-prompt.md` ist unverändert und beschreibt Stufe 2. Die habe ich bereits geliefert (`OCT Wizard Stufe 2.dc.html` und die Dateien in `wizard/`). Angehängt sind aber die Originale für Stufe 3, außerdem Unit-Tests und Acceptance-Checks. Was soll ich bearbeiten?

1. **Stufe 3 bauen**: Schritte 5–8 (Hosts, NTP, Prüfung, Fertig) nach denselben Regeln wie Stufe 2. Dazu gehören TSX, CSS, Prototyp und neue i18n-Keys, und die Unit-Tests und Acceptance-Checks berücksichtige ich.
2. **Stufe 2 überarbeiten**: Dafür brauche ich eure Änderungswünsche oder das Ergebnis eurer Prüfung (`tsc`, ESLint, Acceptance-Checks).
3. **Die Prompt-Datei selbst ändern**: Sagt mir bitte, was darin stehen soll.

Ich vermute Option 1 und warte auf eure Antwort.

## User

Bearbeite wizard-stage3-prompt.md

## Assistant

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

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

_[tool: dc_write]_

_[tool: ready_for_verification]_

Stufe 3 (Schritte 5–8) liegt zur Prüfung vor. Der Prototyp ist `OCT Wizard Stufe 3.dc.html`: Breiten 320, 375, 414, 768 und 1280, ein Zustandswähler pro Schritt und die deutschen Texte aus Anhang 10. Ein Badge prüft automatisch auf Overflow, Überlappung und Tippziele unter 44 px. `tsc` und ESLint habe ich nicht laufen lassen. Die Vorschau rendert HTML, das die TSX-Komponenten spiegelt, nicht die TSX selbst.

**Dateien in `wizard/`** (Icons nur ergänzt)
- Komponenten: `Step6HostsModification.tsx`, `Step7NtpPatch.tsx`, `Step8Verification.tsx`, `Step9Completion.tsx`. Props, Hooks, API-Aufrufe, Timer, `t()`-Keys, Klassen, `id`s und DOM-Reihenfolge sind unverändert, nur das Markup ist neu. Der Countdown läuft weiter über 100 s.
- CSS: je eine Schritt-Datei, mit Selektoren nur unter dem Schritt-Wrapper oder mit Präfix. Die Animation heißt jetzt `wz-celebrate`.
- `wizard-base.css` ist vollständig und baut auf eurer Anhang-4-Version auf. Neu sind `.wizard-step-actions:not(:has(button)) { display: none }`, damit die leere Aktionsleiste im Fertig-Schritt verschwindet, sowie `.failed-*` und `.wz-result--warning`.
- `Icon.tsx` hat neu `Globe`, `Clock`, `Search`, `Rocket`, `PartyPopper` und `HardDrive`.

**Logik- und Verhaltensabweichungen**
- **Hosts-Schritt:** Das Formular bleibt sichtbar, bis `success` gilt (`!modifyData?.success` statt `!modifyData`). Im Original führte `success=false` in eine Sackgasse ohne Wiederholen. Das ist dasselbe Muster wie bei Backup.
- **Prüfschritt:**
  - Neu ist eine dreiteilige Phasenanzeige mit fester Höhe.
  - Alle Statuszeilen haben dieselbe Mindesthöhe, die Zahl hat eine feste Breite, und es gibt einen Fortschrittsbalken ohne Text. Dadurch springt das Layout bei Countdown und Phasenwechsel nicht.
  - `nextDisabledReason` ist neu.
- **Fertig-Schritt:** Ohne Backup-Pfad ist die Karte jetzt gelb statt blau.

**Neue i18n-Keys**

| Key | DE | EN |
|---|---|---|
| `setup.wizard.step8.phaseFinalize` | Einrichten | Setup |
| `setup.wizard.step8.phaseReboot` | Neustart | Restart |
| `setup.wizard.step8.phaseVerify` | Prüfen | Verify |
| `setup.wizard.step8.nextDisabled` | Bitte zuerst alle Prüfungen erfolgreich abschließen. | Please complete all checks successfully first. |

**Tests anpassen**
- `Step6HostsModification`: `getByRole("button", { name: /🌐/ })` findet den Button nicht mehr. Nehmt `{ name: /Modify hosts file now/i }` oder `.hosts-modify-btn`.
- Die Tests für Schritt 7 und 8 (Step7/Step8) brauchen nach meiner Durchsicht keine Anpassung. Sie suchen nach Text wie Finalize, Restart, Verification, Retry und Continue anyway, nicht nach Emoji. Prüft bitte trotzdem, ob die Rolle `status` bei den Prüfergebnissen Abfragen stört.

**Offene Punkte**
- Das Banner im Prüfschritt ist blau getönt, zeigt aber weiterhin das Warndreieck aus `WizardStep`. Ein Info-Icon bräuchte eine Änderung an `WizardStep`.
- `stage2-frame.html` lädt jetzt die Texte aus Anhang 10 und nutzt das neue `wizard-base.css`.

Als Nächstes kommt Stufe 4 (die fünf Restore-Screens), sobald ihr Stufe 3 freigebt.

## User

Bearbeite wizard-stage4-prompt.md

## Assistant

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: read_file]_

_[tool: grep]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: grep]_

_[tool: run_script]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: dc_write]_

_[tool: write_file]_

_[tool: ready_for_verification]_

Stufe 4 (Restore, 5 Screens) liegt zur Prüfung vor. Der Prototyp heißt `OCT Wizard Stufe 4.dc.html`. `tsc` und ESLint habe ich nicht laufen lassen. Die Vorschau spiegelt das TSX-Markup als HTML, sie rendert nicht die TSX selbst.

**Dateien in `wizard/`**
- **Komponenten:** `RestoreChoice.tsx`, `BackupScan.tsx`, `RestoreExecution.tsx`, `RestoreVerification.tsx` und `RestoreCompletion.tsx`. Props, Hooks, Effekte, Timer, Request-Mapping und `t()`-Keys sind unverändert. Auch die Übersetzungs-Helfer und alle Klassennamen aus Abschnitt 6 bleiben erhalten.
- **CSS:** `RestoreSteps.css` ersetzt die alte Datei mit demselben Namen. Die Imports ändern sich nicht. Alle Klassen tragen den Namensraum `backup-scan__`, `restore-*` oder `wz-`.
- **`wizard-base.css`** liegt vollständig vor, auf Basis eures Anhangs 5. Neu sind `.wz-spinner`, `.wz-progress` (auch unbestimmt), `.wz-status-actions` und der Tracker-Status „skipped“.
- **`Icon.tsx`** liegt vollständig vor, mit allen bisherigen Pfaden plus `Sparkles`, `ArchiveRestore`, `SkipForward`, `Minus` und `Loader`.
- **`ProgressTracker.tsx`** ist vollständig geliefert. Der Status `"skipped"` zeigt einen Strich in einem gestrichelten grünen Ring, der Connector danach ist grün.

**Prototyp:** Er hat die Breiten 320, 375, 414, 768 und 1280, einen Zustandswähler pro Schritt und die echten deutschen Texte. Das Badge prüft Overflow, Scrollbars, Überlappung, Tippziele ≥44 px, ≤720 px Breite und die weiße Ziffer im aktiven Schritt.

**Entwurfsentscheidungen:**
- Die Ausführung läuft mit Spinner, gleitendem Balken und Hinweis auf mehrere Minuten.
- Die Zusammenfassung (Erfolg oder Teilfehler) erscheint per CSS-`order` über der Liste. Der Teilfehler hat einen roten Rahmen von 2 px und ist damit mindestens so sichtbar wie der Erfolg.
- Der Countdown hat einen Fortschrittsbalken und `tabular-nums`.

**(a) Neue i18n-Keys**

| Key | DE | EN |
|---|---|---|
| `restore.execution.running_hint` | Dieser Vorgang kann mehrere Minuten dauern (meist 8 bis 9). Lassen Sie diese Seite geöffnet und trennen Sie das Gerät nicht. | This can take several minutes (usually 8 to 9). Keep this page open and do not disconnect the device. |
| `restore.execution.error_hint` | Gehen Sie zurück und versuchen Sie es erneut. | Go back and try again. |
| `restore.execution.failed_title` | Wiederherstellung unvollständig | Restore incomplete |
| `setup.stepAriaSkipped` | Schritt {{id}}: {{label}} — {{description}} – übersprungen | Step {{id}}: {{label}} — {{description}} – skipped |

**(b) Logikabweichungen**
1. **`SetupWizard.tsx`, `restoreTrackerSteps`:** Eine Zeile ändern, damit der Tracker „skipped“ bekommt: `status: skipped ? "skipped" : id < restoreStep ? "completed" : "pending"`.
2. **Fehlerbox bei Teilfehler:** In `RestoreExecution` rendert `data && !data.success` jetzt eine Fehlerbox. Die Daten waren schon vorhanden, es gibt keinen neuen Zustand.
3. **Retry bei Ausführungsfehler:** Ich habe keinen eingebaut. Gebraucht würde ein `restore(request)`-Aufruf aus einem Handler, das entscheidet ihr.

**(c) Tests anpassen**
- Das ✅ im Online-Text ist weg, `.restore-verification__online` enthält jetzt ein Icon und `<p>Gerät ist wieder online!</p>`.
- Das ⚠️ in `.backup-scan__mismatch` ist ein Icon, der Text steht in einem inneren `span`.
- Die Status-Emoji in den Ausführungszeilen sind SVGs.
- In `RestoreCompletion` stehen die Listentexte nun in einem `span` im `li`, die `h5`-Texte ohne Emoji.
- Die Hinweisnotiz ist `p.restore-completion__note` mit einem inneren `span` für den Text.
- Die Retry- und Bestätigen-Buttons haben jetzt `btn`-Klassen. Der Retry-Button enthält zusätzlich ein Icon, sein Name enthält weiter „Retry“.

**(d) Offene Punkte**
- Die Statusicons in den Ausführungszeilen haben keinen Textersatz für Screenreader. Dafür wäre ein Key pro Status nötig.
- Der Countdown-Text ist ein einziger String, die Zahl kann also nicht in einem festen Container stehen. Die Position der Zeile bleibt stabil. Nur das „s…“ kann sich um eine Ziffer verschieben.

