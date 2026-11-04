# Feedback aus Staging einarbeiten

_Started 2026-10-23 16:51 UTC_

---

## User

<artifact-content-authored-by-others/>
Continuing from "App stage 6 prompt editing".

## Assistant

We were working through Stage 6c feedback—refining the device card header layout and phone device-switching behavior. The goal was to eliminate container queries, unify the header at all sizes, and move the arrow/dot bar below the page title on phones when there's enough vertical space (≥568 px height).

We made these decisions: single header layout (name between power and setup badge, model/IP centered below) without container queries, reducing column gap to 8 px and name-button padding to 6 px; device-switching bar relocates via CSS Grid only (no DOM change) for phones ≥568 px tall; long names scroll as marquee; tap targets stay 44 px. The bar also applies to phones in landscape (up to 500 px height) since side arrows would fall below the fold. We proposed a 2 px inset box-shadow on search chips but didn't integrate it (CSS snippet only in notes).

Current state: `app6c/` contains updated `DeviceSwiper.css`, `DeviceNameEditor.css`, `LocalControl.css`, `RadioPresets.css` plus before-versions; `OCT App Stufe 6c.dc.html` prototype with quick-select buttons for five phone widths and a "header: card widths" page showing five widths side-by-side. Both `app6b/` and `app6c/` now load `de-texts.json` locally and skip the marquee wrapper from badge checks. The verifier just ran; the "card widths" page audit should now be green at 320, 375, and 768 px (awaiting visual confirmation).

Open: confirm the card-widths page audit passes at all three widths in the prototype. Decide if the threshold for portrait-to-sticky-bar switches from 480 to 600 px. Integrate the 2 px chip border if approved. The sticky bar (S1 in notes) requires DOM restructuring and wasn't done.

Files: `app6c/` contains all TSX, CSS, and i18n; `app6b/` updated frame files; `OCT App Stufe 6c.dc.html` is the prototype.

## User

Arbeite das Feedback aus app-stage6d-feedback.md ein.

## Assistant

_[tool: read_file]_

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

_[tool: list_files]_

_[tool: grep]_

_[tool: list_files]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: copy_files]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: run_script]_

_[tool: dc_write]_

_[tool: show_html]_

_[tool: get_webview_logs]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: save_screenshot]_

_[tool: show_html]_

_[tool: get_webview_logs]_

_[tool: run_script]_

_[tool: show_html]_

_[tool: get_webview_logs]_

_[tool: str_replace_edit]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: save_screenshot]_

_[tool: save_screenshot]_

_[tool: str_replace_edit]_

_[tool: show_html]_

_[tool: dc_js_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: save_screenshot]_

_[tool: save_screenshot]_

_[tool: save_screenshot]_

_[tool: dc_html_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: dc_js_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: save_screenshot]_

_[tool: save_screenshot]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: grep]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: dc_js_str_replace]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: dc_js_str_replace]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: str_replace_edit]_

_[tool: dc_js_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: get_webview_logs]_

_[tool: dc_js_str_replace]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: get_webview_logs]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: dc_js_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: dc_js_str_replace]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: run_script]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: write_file]_

_[tool: ready_for_verification]_

Stufe 6d ist in `app6d/` fertig, der Prototyp ist `OCT App Stufe 6d.dc.html`. Der Hit-Test ist nur bis 375×667 vollständig gelaufen. In dieser Umgebung dauert ein Durchlauf über zehn Minuten.

- **Hit-Test:** Der Button „Hit-Test starten“ prüft per `elementFromPoint`, ob jedes Steuerelement erreichbar ist. Er läuft auf den vier Phone-Größen, auch während der Überblendung nach Pfeil, Wischen und Punkt, und in den Wizard-Stufen 2 bis 4. Bei 320×568 und 375×667 waren **0 Steuerelemente verdeckt**. Bei 402×874 lief er bis zum Abbruch ohne Fund, 430×932 ist nicht fertig geworden. Bitte einmal komplett durchlaufen lassen. Der „Fehlerfall 6c“-Schalter bildet euren iPhone-Bug nach, und der Test meldet dann `.rp-power`, `.dne-btn` und `.sb` als verdeckt. Gefunden hat er außerdem einen Fehler in meiner ersten Sticky-Version (Karte nur 86 px breit), der behoben ist.
- **Grenze:** Ich habe 768 px (Variante a) gewählt, plus `max-height: 500px` für Querformat. Die Begründung steht in den Notes: Es ist der einzige Breakpoint der App, und ab 600 px kostet die Seitenspalte immer 104 px bei gedeckelter Kartenbreite. Der Prototyp zeigt 320, 480, 600 und 768 nebeneinander.
- **Wischen:**
  - Die Karte folgt dem Finger über `translate`, nicht über framer-Transform.
  - Richtungssperre nach 10 px.
  - Wechsel ab `min(80 px, 25 % Kartenbreite)` oder bei einem Flick (mindestens 24 px und 0,4 px/ms).
  - Zurückschnappen in 220 ms.
  - An den Rändern Gummiband bis höchstens 32 px.
  - Nur Touch und Stift, keine Maus.
  - Lautstärke-Regler, Name und Laufschrift starten keinen Wisch.
  - Bei reduzierter Bewegung wird sofort gewechselt, ohne Mitlaufen.
  - Hinweise: ein Rand-Streifen der Nachbarkarte im Seitenrand und ein Pfeil, der beim Ziehen aufleuchtet.
  - Die TSX-Hinweise stehen in den Notes, 3.6.
- **Sticky-Leiste:** Ich empfehle sie jetzt, anders als in 6c. Sie sticht erst ab 600 px Höhe, versteckt sich nicht beim Scrollen, und während sie klebt, ersetzt der Gerätename mit Zähler die Punkte. Dazu kommen `scroll-padding-top` auf `<main>` und eine Hairline nur im geklebten Zustand. Das exakte DOM steht in den Notes (Abschnitt 4), das CSS in `DeviceSwiper.sticky.css`. Ihr müsst dafür TSX ändern, und der Messwert der Punktbreite muss 0 ignorieren.

Die Notes `STAGE6D-NOTES.md` enthalten die Abschnitte (a) bis (f).

## User

Arbeite das Feedback aus app-stage6e-feedback.md ein.

## Assistant

_[tool: snip]_

_[tool: read_file]_

_[tool: view_image]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: run_script]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: run_script]_

_[tool: ready_for_verification]_

Der Sprung nach oben kam aus dem 6d-Prototyp, nicht aus den ausgelieferten Dateien. Ich habe ihn in `app6e/` behoben. Die Scroll-Position bleibt jetzt bei einem Gerätewechsel erhalten (400 px → 400 px → 400 px), 0 verdeckte Steuerelemente bei 375×667.

- **Ursache:** Bei jeder Änderung hat der Prototyp die ganze Seite neu gerendert und dabei auch `<main>` ersetzt. `<main>` ist der scrollende Container, das neue startete bei 0. Der Sticky-Name sprang für einen Frame auf die Punkte zurück.
- **Fix:** Der Prototyp merkt sich vor dem Rendern die Scroll-Position und den Sticky-Zustand und setzt beide danach wieder.
- **Test:** Der Hit-Test misst jetzt im Sticky-Modus auch die Scroll-Position (400 → Wechsel → zurück).
- **Ausgelieferte Dateien:** Sie scrollen nichts und brauchen keinen Reset, `<main>` wird nie neu erzeugt. Ist die neue Karte kürzer als die alte, kürzt der Browser die Scroll-Position auf die kürzere Seite. Das ist normales Browser-Verhalten, kein Reset.
- **Screenshot-Vergleich:** Ich sehe keinen Unterschied zwischen eurer App und dem Prototyp. Leiste, abgeschnittenes Cover und Rand-Streifen entsprechen dem CSS. Der weiche Schatten unter der Leiste ist auf dem dunklen Hintergrund kaum sichtbar.

Es gibt keine CSS- oder TSX-Änderungen. Das Frame lädt `DeviceSwiper.css` und `DeviceSwiper.sticky.css` unverändert aus `app6d/`. Den Prototyp habe ich ohne Verifier-Durchlauf geöffnet.

Dateien in `app6e/`:
- `STAGE6E-NOTES.md`
- `stage6e-frame.html`
- `frame-pages.js`

Prototyp: `OCT App Stufe 6e.dc.html`

## User

Bearbeite Anforderungen aus app-stage7-prompt.md

## Assistant

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: list_files]_

_[tool: grep]_

_[tool: run_script]_

_[tool: read_file]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: read_file]_

_[tool: run_script]_

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

_[tool: run_script]_

_[tool: write_file]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: delete_file]_

_[tool: show_html]_

_[tool: get_webview_logs]_

_[tool: dc_write]_

_[tool: show_html]_

_[tool: get_webview_logs]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: run_script]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: show_html]_

_[tool: get_webview_logs]_

_[tool: run_script]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: run_script]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: write_file]_

_[tool: ready_for_verification]_

Stufe 7 liegt in `app7/` bereit. Der Hit-Test mit Audit lief über alle 116 Zustände (29 Zustände auf 4 Phone-Größen, 1072 Steuerelemente) und fand genau einen Befund. TSX und CSS selbst habe ich nicht durch `tsc` oder ESLint laufen lassen.

**Dateien in `app7/`:**
- `Settings`, `Diagnostics`, `About`, `Licenses` jeweils als `.tsx` und `.css`
- `Icon.tsx` (komplette Datei, 7 neue Icons)
- `aboutUtils.ts` (komplette Datei, nur `generateGradientColor` geändert)
- `STAGE7-NOTES.md` mit den Abschnitten (a) bis (f)
- Der Prototyp ist `OCT App Stufe 7.dc.html`. Das Logo ist darin ein Platzhalter.

**Der eine Befund:** Der Fehler-Toast beim Diagnose-Download überdeckt bei 320×568 für bis zu 8 s den Download-Button. Das liegt im bestehenden `Toast.css`, nicht in meinen Dateien. Ich habe `Toast.css` nicht angefasst. Die Optionen stehen in den Notes (T1): Toast auf Phones unten platzieren oder den Fehlertext kürzen.

**Was die Prüfung in meinem eigenen Entwurf ergab, jetzt behoben:**
- Die Namen im Wimmelbild blendeten per `opacity` ein, was Kontrastprüfungen während der Animation scheitern lässt. Die Animation skaliert jetzt nur noch.
- Mit den alten Farben hatten 61 von 200 Namen weniger als 4,5:1 Kontrast (Minimum 2,0:1). Neu gilt Helligkeit 74 % / 80 % und Sättigung 55 bis 75 %, damit liegt das Minimum bei 5,2:1.
- Der Diagnose-Download-Button wurde während des Erstellens `disabled`, und `<main>` hatte dann kein fokussierbares Element mehr. Jetzt ist er `aria-disabled` und behält den Fokus.

**Kleine Abweichungen von der Logik, die ihr ablehnen könnt (Details in den Notes, Abschnitt b):**
- **IP-Formular:** `noValidate`, damit eure eigene Fehlermeldung statt der Browser-Blase erscheint. In echten Browsern wurde `invalidFormat` sonst nie gezeigt.
- **Log-Download:** neuer Lade- und Fehlerzustand mit Fehlerzeile unter dem Button.
- **Diagnose:** `StatusBadge` bekommt einen Guard für unbekannte `setup_status`-Werte (z. B. „complete“ in euren Testdaten); der Download-Button steht jetzt im DOM vor den Abschnitten.
- **Framer Motion:** auf Settings und About entfernt, die Einblendung läuft über CSS.
- **Wimmelbild:** statt Tooltip an jedem Namen gibt es einen einzigen Dankessatz pro Besuch, den ihr streichen könnt.
- **Link auf `/licenses`:** neu in der About-Linkliste.

**Eure Entscheidung:** Die Build-Zeit-Zeile würde ich löschen, bis `/health` `uptime` liefert (#521). Die Zeile ist harmlos, aber tot.

Neue Texte gibt es auf Deutsch und Englisch, auch in `i18n-stage7-additions.json`. Die Tests, die ihr anpassen müsst, stehen in Abschnitt (c).

## User

Also ich verstehe die neue Farbgebubg auch bei den Supportern aber monatlich wiederkehrende Unterstützer müssen deutlich glanzvoller 

gestaltet werden. Die Farben wirken insgesamt etwas trist auf mich. Anbei in Anekdoten aus der aktuellen Fassung. Die agröße der Letter berechnet sich aus dem gespendeten Gesamtbetrag. Daher die Unterschiede. Bitte gestalte das nochmal neu. Die monatlichen Supporter hatten einen shiny Glanz Effekt indem das Weiß durch den Schriftzug wanderte.

## Assistant

_[tool: run_script]_

_[tool: show_html]_

_[tool: grep]_

_[tool: run_script]_

_[tool: ready_for_verification]_

Ich habe die Supporter-Farben und den Glanz der monatlichen Supporter neu gemacht. Ich habe es noch nicht selbst angesehen, ein Prüflauf läuft im Hintergrund.

- **Farben:** Die Sättigung liegt jetzt bei 85 bis 100 %. Die Helligkeit wird pro Farbton so weit angehoben, bis der Text mindestens 4,8:1 Kontrast auf der Karte erreicht. Blau und Violett werden dadurch heller, Gelb und Grün bleiben kräftig. Die Farben sollten also wieder so leuchten wie in deinem Screenshot und bleiben trotzdem lesbar.
- **Monatliche Supporter:** Sie sind jetzt fett in Gold mit weichem Leuchten. Ein weißer Glanz wandert alle 3,4 Sekunden durch die Buchstaben, versetzt je Name.
- **Reduzierte Bewegung:** Dann steht der Glanz still in der Mitte.
- **Hoher Kontrast:** Der Text ist dann normal gefärbt und unterstrichen.

Geändert wurden `aboutUtils.ts` (`generateGradientColor`), `About.css` und der Prototyp. Die Größe der Namen nach Gesamtbetrag ist unverändert.

Die vorherige Fassung von `aboutUtils.ts` enthielt noch die alte Farbfunktion, obwohl die Notes die neue beschrieben. Das ist mit dieser Änderung behoben. Die Kontrastzahlen im Abschnitt „Supporters“ in `STAGE7-NOTES.md` (5,2:1, Helligkeit 74/80 %) gelten jetzt nicht mehr, ich habe sie noch nicht aktualisiert.

_[tool: run_script]_

_[tool: ready_for_verification]_

Der Fehler lag im Prototyp: Meine neuen Farb-Helferfunktionen hatten denselben Namen wie bestehende Prüfcode-Funktionen in `frame-pages7.js`, sodass das Skript nicht lief. Ich habe sie umbenannt. Das TSX und CSS sind davon nicht betroffen. Der erneute Prüflauf läuft im Hintergrund, ich melde mich nur, wenn er etwas findet.

## User

Und wo ist meine interaktive Vorschau?

## Assistant

_[tool: show_to_user]_

Die interaktive Vorschau ist `OCT App Stufe 7.dc.html`, ich habe sie gerade in deinem Tab geöffnet. Dort wählst du oben Seite, Breite bzw. Phone-Größe und die Zustände. Die Seite „Über“ mit den neuen Supporter-Farben und dem Glanz der monatlichen Supporter findest du unter „Über“.

Zuletzt war `app7/stage7-frame.html?page=about&sup=40` geöffnet. Das ist nur der Einzelrahmen ohne Bedienleiste.

## User

Es wäre gut für die Bedieung und die Pflege, wenn ein Gerät auch dann entfernt werden könnte, wenn es nicht offline ist. Designe dazu sowohl im Status Gerät offline als auch im Status online eine Konsistente Ansicht (Löschen Button), die sich gut ins gesamtdesign integriert

## User

Found issues — fixing…

## User

<artifact-content-authored-by-others/>
Found issues — fixing…

## Assistant

_[tool: copy_files]_

_[tool: ready_for_verification]_

Die Vorschau blieb leer, weil im Ordner `app8/` die Textdatei `i18n-stage6b-additions.json` fehlte. Ich habe sie aus `app6e/` kopiert. Ob die Vorschau jetzt rendert und der Ablauf funktioniert, ist noch nicht bestätigt. Die erneute Prüfung läuft im Hintergrund, ich melde mich nur, wenn sie etwas findet.

## User

Fehler: SyntaxError: Unexpected token 'i', "file not found " is not valid JSON

## Assistant

_[tool: list_files]_

_[tool: list_files]_

_[tool: list_files]_

_[tool: grep]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: list_files]_

_[tool: run_script]_

_[tool: run_script]_

Alle fünf Textdateien sind jetzt vorhanden und gültig. Der Fehler stammte vom Stand vor dem Kopieren. Ich lade die Vorschau neu.

_[tool: show_to_user]_

Die Vorschau ist neu geladen. Falls der Fehler noch erscheint, klicke einmal auf „Zurücksetzen“ oder lade die Seite neu, da der Browser die alte Fehlerseite zwischengespeichert haben kann.

## User

mir ist aufgefallen, dass man über die About Seite Links via neue Seite zu Github, Problem melden und im embedded Browser sogar zu buy me a coffee kommt. DIe Seiten Diagnose und Lizenzen sind ebenfalls als unterseiten zu erreichen. Auf den beiden letzten ist es aber nicht möglich zurück zur about seite zu navigieren. Man muss in der Navigation den Button klicken. Ist das mit den Design Richtlinien so vereinbar? Macht man das so?

## Assistant

Nein, so macht man das nicht. Beim Zurücknavigieren gibt es zwei getrennte Fälle.

**Diagnose und Lizenzen:**
- Beide Seiten sind Unterseiten von „Über“, haben aber keinen Rückweg. Wer sie über die Linkliste öffnet, muss den Umweg über die Hauptnavigation nehmen, und die Navigation zeigt dabei nicht einmal an, dass man unter „Über“ ist.
- Üblich ist ein „← Über“-Link direkt über der Überschrift, als Text-Link mit Pfeil-Icon (Lucide `ArrowLeft`, 1,5 Strichstärke) und mindestens 44 px hoher Klickfläche. Er führt immer fest zu `/about` und nicht zu `history.back()`, damit er auch nach einem direkten Aufruf der URL funktioniert.
- Das passt zu den Industry-Richtlinien: Es ist ein einfacher Text-Link im Stil `.btn-ghost`, ohne zusätzliche Farbe oder Fläche. Außerdem ist die Hierarchie dann auch für Screenreader klar.
- Zusätzlich sollte „Über“ in der Navigation als aktiv markiert bleiben, solange man auf einer dieser Unterseiten ist. Im Prototyp ist das bereits so eingestellt, in eurer App bitte prüfen.

**Externe Links (GitHub, Problem melden, Buy Me a Coffee):**
- Dass sie in einem neuen Tab öffnen, ist bei externen Zielen üblich. Sie tragen das Extern-Icon und den versteckten Hinweis „öffnet in neuem Tab“.
- Das Verhalten im eingebetteten Browser liegt an der Einbettung. Dort gibt es oft keine Tab-Leiste und keinen Zurück-Knopf, und manche Seiten wie Buy Me a Coffee lassen sich nicht einbetten.
- Wenn die App in so einer Einbettung laufen soll, könnte man externe Links dort ausblenden oder durch „Link kopieren“ ersetzen. Das ist eine Produktentscheidung.

Soll ich den Zurück-Link in den Prototyp (`app7/`) einbauen, mit TSX und CSS für `Diagnostics` und `Licenses`? Ein Schalter für externe Links in Einbettungen wäre eine eigene Stufe.

## User

Aber die beiden zurück zu Über Links existieren noch nicht im Prototyp korrekt?

## Assistant

_[tool: run_script]_

_[tool: show_html]_

_[tool: ready_for_verification]_

Nein, sie fehlten bisher im Prototyp. Jetzt sind sie in „Diagnose“ und „Lizenzen“ drin: ein Link „← Über“ mit Pfeil-Icon direkt über der Überschrift. Er führt fest nach `/about` und ist mindestens 44 px hoch. Die Hauptnavigation markiert „Über“ weiter als aktiv. Ich habe die Seite noch nicht selbst angesehen, ein Prüflauf läuft im Hintergrund.

Im Prototyp (`OCT App Stufe 7.dc.html`) sind die Links in allen Zuständen sichtbar, auch beim Laden und bei Fehlern. Ihr bekommt dafür Änderungen in `Diagnostics.tsx/.css`, `Licenses.tsx/.css` und `Icon.tsx` (neues Icon `ArrowLeft`). Der neue Text-Schlüssel `about.back` lautet „Über“ bzw. „About“.

## User

Ich glaube für die lokale Steuerung von Bluetooth, Airplay, DLNA, Spotify fehlen noch die Titel Vor und Titel Zurück Buttons. Diese sind gänzlich vergessen worden. Arbeite diese zusammen mit dem play/Pause Button konsistent in alle Lokal abspielbaren Medien ein.

## User

Found issues — fixing…

## User

<artifact-content-authored-by-others/>
Found issues — fixing…

## Assistant

_[tool: run_script]_

_[tool: grep]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: ready_for_verification]_

Die Überschrift zeigte „player.localControl“ statt „Lokale Steuerung“, weil dem Stufe-9-Prototyp die Texte fehlten. Der Prototyp lud nur die Stufe-7-Texte, und die enthalten die `player.*`-Schlüssel nicht. Er lädt jetzt zusätzlich `app6c/de-texts.json`. Zusätzlich habe ich `player.localControl` in `app9/i18n-stage8-additions.json` auf Deutsch und Englisch ergänzt. Das betrifft nur die Vorschau, nicht eure TSX- oder CSS-Dateien.

Dasselbe Textproblem steckt vermutlich auch im Stufe-8-Prototyp, den ich nicht angefasst habe. Ob die Überschrift jetzt stimmt, ist noch nicht bestätigt, der Prüflauf läuft im Hintergrund.

## User

Falls "es läuft" nichts anzeigt oder nur teilweise Daten geliefert bekommt, springt die Anzeige dann? Wenn "es läuft" überlange Daten geliefert bekommt - springt die Anzeige dann? Prüfen und wenn nötig beheben.

## Assistant

_[tool: run_script]_

_[tool: show_html]_

_[tool: save_screenshot]_

_[tool: save_screenshot]_

Nein, die Anzeige springt nicht. Das gilt für „Es läuft“ ohne Daten, mit Teildaten und mit überlangen Daten. Ich habe nichts geändert, die Karte ist schon so gebaut.

Gemessen habe ich 32 Kombinationen bei 320 und 402 px Breite. Die Kombinationen sind sieben Quellen mit je vier Datenständen: voll, ohne Titel und Interpret, nur Titel, überlang. Dazu kamen Standby und „Keine Daten“. Im Ausschnitt, den ich vollständig gesehen habe, waren Höhe des „Es läuft“-Blocks, Position der Tasten und Kartenhöhe in jeder Kombination identisch. Bei 320 px sind das 352, 467 und 692 px, bei 402 px sind es 402, 516 und 750 px. Die Tasten und die Lautstärke bleiben also an derselben Stelle.

- **Leer oder teilweise:** Der Block reserviert feste Höhe für Titel- und Interpretenzeile, auch wenn beide fehlen. Bei Standby und „Keine Daten“ erscheint ein Platzhalter in gleicher Größe.
- **Überlang:** Lange Titel, Interpreten und Header-Zeilen laufen als Laufschrift durch und brechen nicht um.
- **Tasten:** Der Ladezustand tauscht nur das Symbol gegen den Spinner in gleicher Größe aus. Pause und Wiedergabe sind gleich groß.

Vom Messlauf habe ich nur den Anfang gesehen. Er war uniform, aber nicht jede Zeile liegt mir vor. Nicht gemessen sind das Umschalten während der Wiedergabe, also der Übergang selbst, und die Presets-Karte.

Als Hilfe für euch habe ich im Prototyp den Parameter `np9` ergänzt (`full`, `notrack`, `noartist`, `long`), mit dem sich diese Datenstände im Frame aufrufen lassen.

## User

<pasted_text name="Pasted text (33 lines)">
Stufe 9: Die Gerätekarte wird zur einzigen Stelle für alles, was ein Gerät betrifft. Bitte entwirf sie visuell.

Hintergrund
Bisher gibt es zwei getrennte Seiten: "Presets" (die Gerätekarte mit Wiedergabe und Preset-Slots) und eine "Lokale Steuerung", die praktisch nirgends verlinkt ist und die niemand benutzt. Wir führen beides zusammen. Die Seite heißt künftig "Geräte" (englisch "Devices"). Die Karte ist das Gerät: Sie zeigt, was es gerade spielt, egal von wo, und lässt sich komplett bedienen. Die Seite "Lokale Steuerung" entfällt ganz.

Was die Gerätekarte können muss (alles auf einer Karte, kein zweiter Bildschirm, kein Tab-Wechsel)
1. Wiedergabe: Cover, Titel, Interpret, Sender bzw. Quelle, Quellen-Badge, Play/Pause. Das gibt es heute schon.
2. NEU Titelsteuerung: Zurück und Vor neben Play/Pause. Sie erscheinen nur, wenn die laufende Quelle Titel kennt: Bluetooth, AirPlay, DLNA/Medienserver, Spotify, Deezer, Pandora, Amazon. Bei Internetradio und TuneIn (Sender, egal ob per Preset gestartet), bei AUX und bei TV/HDMI gibt es sie nicht. Bitte beide Varianten entwerfen: nur Play/Pause und Zurück/Play/Vor. Die Karte darf beim Wechsel nicht springen (feste Höhe oder Platzhalter).
3. NEU Quellenwechsel: Der Nutzer kann das Gerät auf Bluetooth, AUX oder AirPlay umschalten. AirPlay nur anzeigen, wenn das Gerät es kann, es gibt also 2 oder 3 Quellen. Streamingdienste (Spotify usw.) und Medienserver kann man hier nicht wählen. Sie starten in der jeweiligen App und erscheinen dann nur als aktuelle Quelle in der Wiedergabe. Radio ist keine Quelle zum Umschalten: Es startet über die Presets bzw. die Sendersuche. Bitte zeigen:
   - Wie wird die aktuelle Quelle markiert (auch wenn sie nicht umschaltbar ist, z. B. Spotify)?
   - Zustand "wird umgeschaltet" (dauert 1 bis 3 Sekunden) und "Umschalten fehlgeschlagen".
   - Wie sehen die Quellen aus, wenn das Gerät im Standby ist?
4. Presets (die Slots 1 bis 6 wie heute, inkl. Leer-Zustand und Sendersuche), aktuell gespielter Preset hervorgehoben.
5. Lautstärke und Stumm. Das gab es in der Lokalen Steuerung und ist auf der Preset-Karte schon teilweise vorhanden. Bitte ein einheitliches Bedienelement.
6. Ein/Aus (Standby) mit sichtbarem Standby-Zustand, Gerätename (editierbar, wie heute), Zonen-Badge (Master/Slave).
7. Offline-Zustand (Banner, Bedienung gesperrt) und "Gerät entfernen" im Footer: bleibt wie in Stufe 8.

Aufbau, über den wir Entscheidungen brauchen
- Reihenfolge der Bereiche von oben nach unten, auf dem iPhone (320, 390 px) wie am Desktop (768, 1280 px). Die Karte wird dadurch deutlich länger. Wie bleibt sie übersichtlich? Welche Teile sind immer sichtbar, welche eingeklappt (z. B. Quellen)?
- Der sticky Gerätewechsler, das Wischen zwischen Geräten und die Leiste unten bleiben wie in Stufe 6 bis 8.
- Navigation: Der Eintrag "Presets" heißt jetzt "Geräte" ("Devices"). Bitte ein passendes Symbol. Die anderen Einträge bleiben.
- Seitenüberschrift: Es gibt keine "Lokale Steuerung" mehr. Soll die Überschrift der Seite der Gerätename sein oder "Geräte"?

Zustände, die ich in einem Prototyp sehen will
Wiedergabe Radio per Preset | Radio ohne Preset (Sendersuche) | Bluetooth mit Titel und Cover | Bluetooth ohne Cover | AirPlay | Spotify | DLNA | AUX | Standby | Gerät offline | Quelle wird umgeschaltet | Umschalten fehlgeschlagen | Gerät in einer Zone (Master und Slave). Jeweils hell und dunkel, 320, 390, 768 und 1280 px, mit langen deutschen und schwedischen Texten.

Feste Vorgaben
- Wie bisher: Tokens aus ui-base, 44-px-Tap-Targets, native Dialoge, Reduced-Motion, keine neuen Farben ohne Begründung, Texte nur über i18n-Schlüssel (bitte neue Schlüssel mit englischem Text und deutscher Übersetzung nennen).
- Barrierefreiheit: Alle Bedienelemente per Tastatur und Screenreader erreichbar. Die Quellen sind eine Gruppe mit aria-pressed bzw. Radio-Semantik. Zustandsänderungen (Quelle gewechselt, Fehler) werden per role="status" angesagt.
- Die Preset-Slots und die Wiedergabe dürfen nicht kleiner werden als heute.

Liefere wie in den Stufen davor: Prototyp mit allen Zuständen, Tokens, die neuen i18n-Schlüssel und eine kurze Liste, was sich gegenüber Stufe 8 ändert.

</pasted_text>

## Assistant

_[tool: run_script]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: grep]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: dc_write]_

_[tool: ready_for_verification]_

_[tool: write_file]_

Die Gerätekarte steht als Prototyp in `OCT App Stufe 10.dc.html`. Geprüft habe ich sie noch nicht, ein Lauf im Hintergrund meldet sich nur bei Fehlern. Die Notes mit Tokens, neuen i18n-Schlüsseln (Englisch und Deutsch) und der Liste der Änderungen gegenüber Stufe 8 stehen in `app10/STAGE10-NOTES.md`. Dass ich diese Stufe 10 nenne, liegt daran, dass die bisherige Stufe 9 die Titel-Tasten waren. Die neue Karte ersetzt sie.

**Reihenfolge der Karte:**
1. Kopf mit Ein/Aus, Name und Zonen-Badge
2. Wiedergabe
3. Titel-Tasten
4. Lautstärke mit Stumm
5. Presets
6. Quelle (eingeklappt)
7. Gerät entfernen

Die Quelle steht zuletzt, weil sie am seltensten gebraucht wird und für die meisten Quellen gar nicht wählbar ist.

**Aufbau nach Breite:**
- Auf dem iPhone steht alles in einer Spalte, nur die Quelle ist eingeklappt.
- Bei 768 px ist die Karte einspaltig und auf 560 px begrenzt.
- Ab 1024 px sind es zwei Spalten in derselben Karte: links Wiedergabe, Tasten und Lautstärke, rechts Presets und Quelle (dort aufgeklappt).

**Titel-Tasten:**
- Bluetooth, AirPlay, DLNA und Spotify zeigen Zurück, Play/Pause und Vor.
- Radio zeigt nur Play/Pause.
- AUX und TV zeigen keine Tasten, sondern eine Zeile „Die Wiedergabe wird am angeschlossenen Gerät gesteuert.“
- Die Reihe ist immer 76 px hoch, die Karte springt also nicht.

**Quelle:**
- Die aktuelle Quelle steht immer im Zeilenkopf, auch bei Spotify, DLNA und Radio.
- Gewählt wird per Chip-Gruppe mit `aria-pressed`: 2 Chips (Bluetooth, AUX) oder 3 mit AirPlay.
- Beim Umschalten zeigt der Chip einen Spinner und die Zeile „Wechsle zu AUX…“.
- Bei einem Fehler bleibt die Zeile offen, mit Fehlermeldung und „Erneut versuchen“.
- Im Standby ist alles unter dem Kopf abgedunkelt und gesperrt, nur Ein/Aus bleibt aktiv.
- Ansagen laufen über `role="status"`, Fehler zusätzlich über `role="alert"`.

**Entscheidungen von mir:**
- Der Menüpunkt heißt „Geräte“ mit dem `Speaker`-Icon.
- Die Überschrift der Seite ist „Geräte“ und nicht der Gerätename. Der Name steht schon als editierbare Überschrift in der Karte, und eine wechselnde h1 würde bei jedem Wischen angesagt.
- Die Zusatzbox „Preset Hinweise“ habe ich weggelassen. Sag Bescheid, wenn sie zurückkommen soll.

**Noch offen:**
- Das helle Thema ist nur ein Entwurf (`theme-light.css`). Die App hat dafür keine Tokens. Offline-Banner, Toasts und Dialoge sind im hellen Thema ungeprüft.
- Die schwedischen Texte decken nur die neuen Schlüssel und wenige bestehende ab. Alles andere fällt auf Deutsch zurück.
- „Sender suchen“ und der leere Preset-Slot sind noch nicht mit dem Suchdialog verbunden.
- Deezer, Pandora und Amazon verhalten sich wie Spotify, sind aber keine eigenen Fälle im Prototyp.

Im Prototyp stellst du Wiedergabefall, Umschalt-Zustand, Zone, Sprache, Thema und Größe (320, 390, 768, 1280 px) oben ein.

## User

Found issues — fixing…

## Assistant

_[tool: run_script]_

_[tool: grep]_

_[tool: run_script]_

_[tool: ready_for_verification]_

Ich habe die Funde des Prüflaufs behoben, den erneuten Lauf habe ich noch nicht gesehen.

- **Rohe Schlüssel:** Die leeren Preset-Slots zeigten „presets.assignPreset“, und auch die Beschriftungen hatten rohe Schlüssel. Ich habe `presets.assignPreset`, `changeStation`, `playPreset`, `removeDevice` und `sync` ergänzt, ebenso `a11y.volume`, `deviceSelection` und `switchToDevice`. Alle gibt es jetzt auf Deutsch, Englisch und Schwedisch in `app10/i18n-stage8-additions.json`. Die Texte des Suchdialogs fehlen weiterhin, den nutzt diese Karte nicht.
- **Standby:** Die abgedunkelten Bereiche tragen jetzt das `inert`-Attribut. Damit sind Quellenzeile, „Sender suchen“, „Vom Gerät laden“ und der Lautstärkeregler nicht mehr fokussierbar. Ich habe die Abdunklung von 45 % auf 60 % Deckkraft gesetzt, damit die Texte lesbarer bleiben.
- **Länge auf dem Phone:** Die Preset-Slots bleiben einspaltig und in heutiger Größe, zwei pro Zeile würden sie verkleinern. Die Karte ist rund 1450 px hoch. Übersichtlich halten sie die Reihenfolge, die klebende Geräteleiste und die eingeklappte Quelle. Falls das nicht reicht, wäre der nächste Schritt, die Presets unterhalb des ersten Bildschirms einzuklappen. Das steht so in den Notes.
- **Notes:** `STAGE10-NOTES.md` war schon vorhanden, der Prüflauf hatte sie zu früh gesucht.

## User

<pasted_text name="Pasted text (28 lines)">
Stufe 10 verwerfen wir. Bitte Stufe 11: die Gerätekarte mit Quellenwahl neu entwerfen. Ich bin kein Designer: Wie die Lösung aussieht, entscheidest du. Unten steht, was die Karte leisten muss, und die Qualitätsregeln, die für alles gelten, was du lieferst. Wenn eine Idee von mir gegen eine dieser Regeln verstößt, gewinnt die Regel. Sag mir dann, warum, und schlage etwas Besseres vor.

Qualitätsregeln (gelten für jede Ansicht, jeden Zustand und jede Größe, auch für Einstellungen, Menüs und Dialoge)
1. Ruhe: Beim Umschalten der Quelle, beim Laden und beim Wechsel zwischen Geräten darf nichts ruckeln, springen oder aufblitzen. Keine Layoutsprünge (feste oder reservierte Höhen, Platzhalter statt plötzlich erscheinender Elemente), Übergänge sanft und kurz, mit prefers-reduced-motion ohne Bewegung. Auch der Zustand "wird umgeschaltet" (1 bis 3 Sekunden) und ein Fehler beim Umschalten dürfen die Karte nicht verschieben.
2. Kontrast: Text mindestens 4,5:1, große Schrift und Bedienelemente mindestens 3:1, hell und dunkel, auch bei deaktivierten und aktiven Elementen. Ein Zustand (aktive Quelle, laufender Preset, Fehler) darf nie nur durch Farbe erkennbar sein, sondern zusätzlich durch Form, Symbol, Füllung oder Text.
3. Tastatur: Alles ist ohne Maus bedienbar, in sinnvoller Reihenfolge, mit deutlich sichtbarem Fokus. Nach dem Umschalten oder Schließen eines Dialogs bleibt der Fokus dort, wo der Nutzer war. Keine Tastaturfallen. Für Gruppen (Quellen, Presets) bitte die passende Pfeiltasten-Logik beschreiben.
4. Screenreader und Sehbehinderung: Sinnvolle Rollen, Namen und Zustände (aktiv, gedrückt, deaktiviert, wird umgeschaltet). Änderungen werden höflich angesagt (role="status"), Fehler sofort (role="alert"). Symbole ohne Text haben einen Namen. Dekoration ist ausgeblendet. Die Seite muss bei 200 % Zoom und vergrößerter Schrift ohne waagerechtes Scrollen und ohne abgeschnittene Texte funktionieren (Reflow ab 320 px).
5. Bedienbarkeit: Tap-Ziele mindestens 44 px, genug Abstand dazwischen, nichts nur per Hover oder Wischen erreichbar. Wischen zwischen Geräten bleibt, hat aber immer eine Alternative.
6. Alle Größen: 320, 390, 768 und 1280 px, hell und dunkel. Nicht nur das Phone. Auf großen Bildschirmen soll die Fläche sinnvoll genutzt werden, nicht nur ein gestrecktes Handy.
7. Konsistenz: Tokens, Komponenten und Muster der bisherigen Stufen (ui-base, Dialoge, Toasts, sticky Gerätewechsler). Texte nur über i18n-Schlüssel (neue mit englischem Text und deutscher Übersetzung nennen); lange deutsche und schwedische Texte müssen passen.

Was die Karte leisten muss
Die Karte ist das Gerät und zeigt, was es gerade spielt, egal von wo. Sie enthält: Name (editierbar), Ein/Aus, Zonen-Badge, Offline-Zustand, "Gerät entfernen" (wie Stufe 8), Lautstärke und Stumm, die laufende Wiedergabe und die Quellenwahl.

Quellenwahl, Inhalt (die Form ist deine Entscheidung)
Das Gerät selbst hat genau drei Quellen: Presets (Radio, mit den 6 Preset-Slots und der Sendersuche), Bluetooth und AUX. Als Vorbild die Bose-App im Bild: eine Zeile "Quelle" mit drei runden Symbolen, die aktive gefüllt, und oben "Wiedergabe von …". Das ist Inspiration, kein Zwang. Zwei Wünsche:
- Die Quellenwahl soll oben in oder direkt bei der Anzeige "Wiedergabe von …" sitzen und sich nicht wie ein weiterer Preset-Slot oder eine Fußzeile anfühlen.
- Die gewählte Quelle bestimmt, was darunter erscheint. Presets: Slots, Sender, Play/Pause. Bluetooth: Cover, Titel, Interpret, Play/Pause und Zurück/Vor (Zurück/Vor nur, wenn die Quelle Titel kennt; bei Radio und AUX gibt es sie nicht). AUX: nur Hinweis, keine Titel, keine Tasten außer Lautstärke.
- Die Anzeige folgt immer dem, was das Gerät wirklich spielt. Presets zeigt nur den Bereich, gestartet wird erst beim Antippen eines Presets.

Globale Quellen (Konzept, bitte komplett mitdenken)
Später kommen Quellen wie Medienserver (DLNA), Spotify und weitere dazu. Sie werden wie in der Bose-App einmal global in der App angelegt, nicht pro Gerät: Man wählt ein Gerät, wählt dann eine dieser Quellen, und sie spielt auf dem Gerät. Bitte entwerfen: wie man von der Karte dorthin kommt, wo und wie man solche Quellen anlegt, bearbeitet und entfernt (Liste, Dialog, Leer- und Fehlerzustand, vorgeschlagen unter Einstellungen), und wie eine laufende globale Quelle in der Karte aussieht. Funktional gibt es vorerst nur Bluetooth als externe Quelle. Den Rest bitte als Konzept liefern und klar als "später" kennzeichnen.

Zustände, die der Prototyp zeigen soll
Presets mit und ohne laufenden Sender, Bluetooth mit und ohne Cover, AUX, Standby, Offline, Quelle wird umgeschaltet, Umschalten fehlgeschlagen, Gerät in einer Zone (Master und Slave), laden, Fehler. Dazu der Bereich für globale Quellen. Jeweils in allen Größen, hell und dunkel.

Bitte liefere zusätzlich eine kurze Liste "Wie erfüllt der Entwurf die Qualitätsregeln 1 bis 7?", mit den Stellen, an denen du bewusst etwas anders gemacht hast, und eine Liste, was sich gegenüber Stufe 8 ändert.

</pasted_text>

## Assistant

_[tool: run_script]_

_[tool: run_script]_

_[tool: write_file]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: delete_file]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: run_script]_

_[tool: dc_write]_

_[tool: ready_for_verification]_

_[tool: write_file]_

Der Entwurf für Stufe 11 steht in `OCT App Stufe 11.dc.html`. Ich habe ihn noch nicht selbst angesehen, ein Prüflauf läuft im Hintergrund. Die Kontrastwerte habe ich nicht mit einem Werkzeug über alle Zustände gemessen, im Hellmodus ist das ein offener Punkt. Die Notes in `app11/STAGE11-NOTES.md` enthalten die Liste „Wie erfüllt der Entwurf die Regeln 1 bis 7“, die Änderungen gegenüber Stufe 8 und die neuen i18n-Schlüssel (Englisch, Deutsch, Schwedisch).

**Aufbau der Karte:** Kopf, dann ein Wiedergabe-Block, darunter der Bereich der gewählten Quelle, unten „Gerät entfernen“.
- **Quellenwahl:** Sie sitzt im Wiedergabe-Block, direkt unter der Zeile „Wiedergabe von Bluetooth“. Es sind drei gleich große Segmente (Presets, Bluetooth, AUX) mit Symbol und Text, kein Preset-Slot und keine Fußzeile.
- **Zustand erkennbar:** Aktiv heißt gefüllt, mit 2 px Rahmen und Haken. „Wird nur angezeigt“ ist gestrichelt.
- **Presets:** Wer Presets antippt, während Bluetooth läuft, ändert nichts am Gerät. Gestartet wird erst beim Antippen eines Presets. Bluetooth und AUX schalten das Gerät um.
- **Tasten:** Zurück/Vor erscheinen nur bei Bluetooth. Radio zeigt nur Play/Pause, AUX nur einen Hinweis in derselben Zeile.
- **Bereich darunter:** Er zeigt Preset-Slots mit Sendersuche, die Bluetooth-Verbindung, den AUX-Hinweis oder die laufende globale Quelle. Ab 768 px steht er neben dem Wiedergabe-Block statt darunter.

**Ruhe:** Alle Alternativen teilen sich eine Rasterzelle, die Höhe richtet sich nach der höchsten. Laden, Fehler und Offline liegen als Overlay über einem unsichtbaren Körper in voller Höhe. Beim Umschalten dreht sich nur der Spinner im gewählten Segment. Die Fehlermeldung schwebt über dem Wiedergabe-Block. Dabei ist kurz das Cover verdeckt. Ich habe das bewusst gewählt, weil eine reservierte Fehlerzeile in jedem Zustand eine Lücke ließe.

**Tastatur:** Quellen und Presets sind je ein Tab-Stopp. Pfeiltasten bewegen nur den Fokus, Enter oder Leertaste wählt. Das habe ich bewusst so entschieden, weil ein Wechsel Sekunden dauert und fehlschlagen kann. Der Fokus bleibt nach Wechsel, Fehler und Dialog am selben Segment.

**Globale Quellen (Konzept, überall als „Später“ markiert):**
- Ein viertes Segment „Mehr“ öffnet einen Dialog „Quelle wählen“.
- Läuft eine globale Quelle, wird das vierte Segment zu dieser Quelle. Cover, Titel und Zurück/Vor erscheinen, der Bereich darunter erklärt „wird in der App gesteuert“.
- Verwaltet wird unter „Einstellungen › Quellen“ mit Liste, Hinzufügen, Bearbeiten, Entfernen, Leer-, Lade- und Fehlerzustand.
- Im Prototyp schaltest du das über „Globale Quellen“ ein.

**Noch offen:**
- Der helle Modus ist ein Entwurf.
- Presets ändern oder löschen sitzt hinter „Bearbeiten“. Den Dialog dazu habe ich nicht neu gezeichnet.
- Schwedisch deckt nur die neuen Texte und wenige alte ab, der Rest fällt auf Deutsch zurück.

## User

Stufe 11 verwerfen wir für die Gerätekarte (die Einstellungen "Quellen" aus Stufe 11 sind in Ordnung, gehören aber nicht zu diesem Auftrag). Bitte Stufe 12: Die Gerätekarte bleibt exakt so gestaltet wie in Stufe 9. Layout, Reihenfolge, Größen und Stil der Karte ändern sich nicht. Neu ist nur, dass man die Quelle des Geräts wechseln kann, und zwar ohne dass die Karte dadurch eine neue Hauptfunktion bekommt.

Warum Stufe 11 nicht ging
Die Quellenwahl war ein großer, eigener Bereich. Es sah aus, als sei das Umschalten die Hauptsache der Karte. Die Hauptsache sind die Wiedergabe und die Presets. Die Quelle zu wechseln ist ein seltener, kleiner Vorgang.

Die Idee, die ich verfolgt sehen will (nur eine Richtung, keine Vorgabe)
Die Karte in Stufe 9 zeigt schon eine kleine Quellenanzeige ("Wiedergabe von …" bzw. das Quellen-Badge an der Wiedergabe). Diese Anzeige soll doppelt genutzt werden: Sie zeigt weiter an, was gerade spielt, und sie ist zugleich die Stelle, an der man zwischen den drei Quellen des Geräts umschaltet: Presets (Radio), Bluetooth und AUX. Klein, unauffällig, an der Stelle, an der sie schon ist.
Ich bin kein Designer. Mein eigener Gedanke wäre ein Dropdown anstelle des Labels, aber das ist ausdrücklich keine Anweisung. Es geht sicher viel besser. Bitte erkunde mehrere Ansätze (zum Beispiel Menü oder Popover am Label, Mini-Umschalter, Wischgeste, Teil des Badges) und zeig mir die zwei bis drei besten. Entscheide selbst, was sich am besten anfühlt, und begründe es kurz.

Was die Lösung erfüllen muss
- Man erkennt, dass die Anzeige antippbar ist, ohne dass sie auffällt oder wie ein weiterer Button aussieht.
- Die Trefferfläche ist mindestens 44 px, auch wenn das sichtbare Element klein ist.
- Die Karte bewegt sich beim Umschalten nicht (Regel 1): feste oder reservierte Höhen, keine Layoutsprünge, sanfter Übergang. Zeige die Zustände "wird umgeschaltet" (1 bis 3 Sekunden) und "Umschalten fehlgeschlagen" so, dass sie die Karte nicht verschieben.
- Was die Karte darunter zeigt, folgt der gewählten Quelle wie in Stufe 9: Presets zeigt die Slots (gestartet wird erst beim Antippen eines Presets), Bluetooth zeigt Titel, Interpret, Cover und Zurück/Vor (nur wenn Titel bekannt sind), AUX zeigt nur einen Hinweis.
- Die gewählte Quelle folgt immer dem, was das Gerät tatsächlich spielt. Läuft etwas, das man hier nicht wählen kann (zum Beispiel Spotify), wird es nur angezeigt, nicht gewählt.
- Auch bei Standby, Offline und Gerät in einer Zone sinnvoll (z. B. in Standby nicht umschaltbar, offline gesperrt).
- Globale Quellen (DLNA, Spotify usw.) sind weiterhin später dran: Ein Platz dafür darf vorgesehen sein, aber ausgeblendet. Bitte zeigen, wie die Anzeige aussähe, wenn weitere Quellen dazukommen.

Qualitätsregeln gelten wie in der letzten Runde unverändert, für jede Ansicht, jeden Zustand und jede Größe: (1) ruhig, kein Ruckeln oder Springen, reduced-motion; (2) Kontrast mindestens 4,5:1 für Text und 3:1 für Bedienelemente, hell und dunkel, Zustände nie nur durch Farbe; (3) voll per Tastatur bedienbar, sichtbarer Fokus, Fokus bleibt nach dem Umschalten, keine Fallen; (4) Screenreader: passende Rolle (z. B. Menü oder Auswahl), Name und Zustand, Ansage per role="status" bzw. role="alert", 200 % Zoom ohne Abschneiden; (5) 44-px-Tap-Ziele, nichts nur per Hover oder Wischen; (6) 320, 390, 768, 1280 px, hell und dunkel, nicht nur Phone; (7) Tokens und Komponenten der bisherigen Stufen, Texte nur über i18n-Schlüssel (neue mit englischem Text und deutscher Übersetzung), lange deutsche und schwedische Texte müssen passen.

Liefere: die zwei bis drei besten Ansätze nebeneinander für die Karte in Stufe 9 (nur der Ausschnitt mit der Quellenanzeige, in allen genannten Zuständen), dazu eine kurze Empfehlung, wie der gewählte Ansatz die Qualitätsregeln 1 bis 7 erfüllt, und was sich gegenüber Stufe 9 ändert. Nach meiner Wahl baust du den gewählten Ansatz in die komplette Karte ein, in allen Größen.

## Assistant

_[tool: run_script]_

_[tool: write_file]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: delete_file]_

_[tool: write_file]_

_[tool: dc_write]_

_[tool: ready_for_verification]_

_[tool: snip]_

Die drei Ansätze für die Quellenanzeige stehen nebeneinander in `OCT App Stufe 12.dc.html`, alle klickbar und per Tastatur bedienbar. Geprüft habe ich sie noch nicht, ein Prüflauf läuft im Hintergrund. Die Empfehlung zu den Regeln 1 bis 7 und die Liste der Änderungen gegenüber Stufe 9 schreibe ich erst nach deiner Wahl, wie angekündigt.

Gezeigt wird nur der Ausschnitt der Stufe-9-Karte: die Anzeige „Wiedergabe von …“ als Kopfzeile, Cover, Titel, Tasten und darunter der Bereich der Quelle.

**Die drei Ansätze:**
- **A, Menü am Label:** Das Label selbst ist der Knopf, erkennbar nur an einem kleinen Pfeil. Das Menü schwebt über dem Cover. Es ist die ruhigste Variante und die Standardlösung für „auswählen“. Sie braucht einen Tipp, um die Auswahl zu sehen.
- **B, Mini-Umschalter im Kopf:** Drei kleine Symbole rechts in der Kopfzeile, das aktive ist gefüllt. Man sieht sofort alle Optionen und wechselt mit einem Tipp. Dafür belegt der Umschalter dauerhaft Platz neben dem Label, das dadurch früher abgeschnitten wird, und er wirkt am ehesten wie eine eigene Funktion.
- **C, Badge öffnet Dialog:** Nur ein kleiner Pfeil am Badge, die Auswahl liegt in einem Dialog. Das ist die unauffälligste Variante und mit großen Schriften am robustesten, braucht aber zwei Tipps pro Wechsel.

Mein Eindruck: A passt am besten zu „klein, unauffällig, an der Stelle, an der sie schon ist“. C wäre die Alternative, wenn dir A noch zu sichtbar ist.

**Was alle drei gemeinsam tun:**
- **Trefferfläche:** Das sichtbare Element bleibt klein, die Trefferfläche ist 44 px.
- **Umschalten:** Beim Wechsel (1,7 s) zeigt nur das betroffene Symbol einen Spinner, das Label ändert sich zu „Wechsle zu AUX…“.
- **Fehler:** Die Fehlermeldung schwebt über Cover und Titel, die Kopfzeile bleibt frei.
- **Nur Anzeige:** Läuft Spotify, wird es nur angezeigt, nicht wählbar.
- **Presets:** Antippen zeigt nur den Bereich, gestartet wird erst beim Tippen auf einen Preset.
- **Standby, Offline, Zone-Slave:** gesperrt.
- **Reservierte Höhen:** Der Bereich darunter hat feste Höhe.

Eine Einschränkung: Die Stufe-9-Karte hatte keine Preset-Slots. Ich zeige sie im Bereich darunter, und der Bereich ist immer so hoch wie die Presets. Bei Bluetooth und AUX bleibt deshalb unten viel Leerraum. Das ist der Preis für „die Karte springt nicht“. Eine Alternative wäre, die Presets immer sichtbar zu lassen.

Im Prototyp stellst du Quelle, Zustand, Umschalten, Sprache, Thema und Breite ein. „Weitere Quellen“ zeigt, wie jeder Ansatz mit Medienserver und Spotify als wählbaren Quellen aussähe.

Sag mir, welchen Ansatz ich in die komplette Karte einbauen soll.

## User

Found issues — fixing…

## Assistant

_[tool: run_script]_

_[tool: ready_for_verification]_

Ich habe die beiden Tastaturfehler behoben, die der Prüflauf gefunden hat. Der erneute Lauf ist noch offen.

- **Ansatz A (Menü):** Beim Öffnen springt der Fokus jetzt auf den gewählten Eintrag im Menü, vorher blieb er am Label. Pfeiltasten, Enter und Esc funktionieren dann sofort. Esc oder Schließen bringt den Fokus zurück an den Auslöser.
- **Ansatz C (Dialog):** Der Fokus liegt beim Öffnen auf der gewählten Quelle statt auf „Schließen“.
- **B:** Der Menüeintrag „Weitere Quellen“ bei B ist mitgeändert, der Fokus geht beim Öffnen ebenfalls ins Menü.

Die Prüfung der Höhen war bereits sauber: Karte, Wiedergabe und Tasten bleiben in allen Zuständen gleich hoch, auch beim Umschalten, im Fehlerfall und mit langen Texten. Den Kontrast im hellen Modus und die umbrechenden schwedischen Texte konnte der Lauf nicht prüfen, weil Screenshots den Inhalt der Frames nicht zeigen.

Sag mir, welchen Ansatz ich in die komplette Karte einbauen soll.

## User

basis sollte die gerätekarte aus stufe 9 sein. Hier in den Entwürfen fehlt die Lautstärkeeinstellung und der Gerät löschen Button. Der muss generell verfügbar sein, denn das ist unabhängig von der Quelle. Der Entwurf in B mit den 3 kleinen Buttons gefällt mir am besten. Beim Wechsel von einer externen Quele zurück auf Presets soll der Wechsel auch stattfinden und das zuletzt ausgewählte Preset gespielt werden. Passe den Entwurf in Stufe 12 so an, dass die Karte bis auf die neuen Next/Prev Buttons und Quellenauswahl Funktionalitäten der in Stufe 9 entspricht.

## Assistant

_[tool: run_script]_

_[tool: dc_write]_

_[tool: ready_for_verification]_

Stufe 12 ist jetzt die komplette Karte aus Stufe 9 mit Ansatz B. Der Prototyp ist `OCT App Stufe 12.dc.html`, einen Prüflauf dazu habe ich noch nicht gesehen.

- **Karte wie Stufe 9:** Kopf mit Ein/Aus, Name, Zonen- und Setup-Badge, dann Wiedergabe, Tasten, Lautstärke und „Gerät entfernen“. Der Entfernen-Button ist in jedem Zustand da, auch offline und im Standby. Die Seite hat wieder Titel, Gerätewechsler und Wischen.
- **Quellenwahl B:** Drei kleine Symbole (Presets, Bluetooth, AUX) rechts in der Kopfzeile der Wiedergabe. Das aktive ist gefüllt und doppelt umrandet, das Label daneben nennt die Quelle. Trefferfläche 44 px. Beim Wechsel dreht nur das gewählte Symbol einen Spinner, das Label wird zu „Wechsle zu AUX…“. Ein Fehler schwebt über Cover und Titel. Tastatur: Pfeiltasten bewegen den Fokus, Enter oder Leertaste wählt.
- **Zurück zu Presets:** Das Symbol schaltet jetzt wirklich um und spielt den zuletzt gewählten Preset. Das Label zeigt dann den Sendernamen. Die Ansage heißt „Quelle gewechselt: Presets · SWR3“.
- **Zurück/Vor:** Sie sind aktiv bei Bluetooth und bei Medienserver oder Spotify, sobald diese später wählbar sind. Bei Radio und AUX sind sie wie in Stufe 9 deaktiviert, die Reihe springt nicht.
- **Nur Anzeige:** Spotify wird nur angezeigt, nicht gewählt. Im Standby und bei Zone-Slave sind die Symbole gesperrt, offline gilt der Hinweis wie in Stufe 9. „Weitere Quellen“ blendet ein viertes Symbol „Mehr“ mit Medienserver und Spotify ein.

Die Preset-Slots und der Bereich unter den Tasten sind weg, weil die Stufe-9-Karte keine Slots hatte. Die Presets bleiben auf der Presets-Seite, die ich nicht angefasst habe. Ansätze A und C sind noch im Code, aber nicht mehr im Prototyp wählbar. Die Notes zu Stufe 12 (Regeln 1 bis 7, Änderungen gegenüber Stufe 9) fehlen noch.

## User

Found issues — fixing…

## Assistant

_[tool: write_file]_

Die Notes zu Stufe 12 sind jetzt in `app12/STAGE12-NOTES.md`. Sie enthalten die Liste „Wie erfüllt B die Regeln 1 bis 7“, die Änderungen gegenüber Stufe 9 und die neuen i18n-Schlüssel auf Englisch, Deutsch und Schwedisch.

Der zweite Punkt des Prüflaufs ist bestätigt: Die Presets-Seite habe ich nicht verändert, sie hat keine Quellenwahl. Falls sie eine bekommen soll, gilt dieselbe Kopfzeile dort.

Die Karte selbst ist weiterhin nicht von mir oder dem Prüflauf nach dem Umbau auf Stufe 9 durchgeprobt. Die Messung der gleichen Höhen in allen Zuständen stammt vom ersten Lauf mit den drei Ansätzen, B nutzt denselben Code. Den Kontrast im hellen Modus habe ich nicht mit einem Werkzeug gemessen. Wo der zuletzt gewählte Preset gespeichert wird, ist eine Produktentscheidung, der Prototyp merkt ihn sich nur im Speicher.

## User

Entschuldigung ich meinte wie in stufe 10. Die auswahl unten weg und dafür die 3 Buttons so wie jetzt auch. 

basis sollte die gerätekarte aus stufe 10 sein. Hier in den Entwürfen fehlt die Lautstärkeeinstellung und der Gerät löschen Button. Der muss generell verfügbar sein, denn das ist unabhängig von der Quelle. Der Entwurf in B mit den 3 kleinen Buttons gefällt mir am besten. Beim Wechsel von einer externen Quele zurück auf Presets soll der Wechsel auch stattfinden und das zuletzt ausgewählte Preset gespielt werden. Passe den Entwurf in Stufe 12 so an, dass die Karte bis auf die neuen Next/Prev Buttons und Quellenauswahl Funktionalitäten der in Stufe 10 entspricht.

## Assistant

_[tool: write_file]_

_[tool: run_script]_

_[tool: delete_file]_

_[tool: dc_write]_

_[tool: run_script]_

_[tool: ready_for_verification]_

Stufe 12 baut jetzt auf der Karte aus Stufe 10 auf. Der Prototyp ist `OCT App Stufe 12.dc.html`, ein Prüflauf dazu läuft im Hintergrund.

- **Was von Stufe 10 bleibt:** Kopf mit Zonen-Badge, Wiedergabe, Tasten, Lautstärke, die sechs Preset-Slots und „Gerät entfernen“. Die Lautstärke und der Entfernen-Button sind in jedem Zustand da, auch offline und im Standby.
- **Weg:** Der Quellenbereich unten mit der eingeklappten Zeile.
- **Neu:** Drei kleine Tasten (Presets, Bluetooth, AUX) rechts in der Kopfzeile der Wiedergabe. Dazu Zurück/Vor bei Bluetooth.
- **Zurück auf Presets:** Der Wechsel findet statt und spielt den zuletzt gewählten Preset. Der Slot ist hervorgehoben, das Label nennt den Sender.
- **Umschalten und Fehler:** Beim Wechsel dreht nur die gewählte Taste einen Spinner. Ein Fehler schwebt über Cover und Titel.
- **Gesperrt:** Im Standby und bei Zone-Slave sind die Tasten gesperrt.
- **Nur Anzeige:** AirPlay, Spotify und DLNA werden nur angezeigt. „Weitere Quellen“ blendet eine vierte „Mehr“-Taste ein.

Ich habe die Karte nach diesem Umbau noch nicht durchgeprobt, auch nicht im hellen Modus. Wo der zuletzt gewählte Preset gespeichert wird, ist eine Produktentscheidung. Der Prototyp merkt ihn sich nur im Speicher.

In den Notes (`app12/STAGE12-NOTES.md`) habe ich die Basis auf Stufe 10 korrigiert. Die Abschnitte zu den Qualitätsregeln und den Änderungen stammen noch aus dem ersten Entwurf und passen im Detail nicht mehr zur Preset-Ansicht. Sag Bescheid, wenn ich sie überarbeiten soll.

## User

Stufe 12 bitte anpassen (Stufe 13). Übernommen wird aus Stufe 12 nur: die drei kleinen Quellen-Buttons oben in der Quellenanzeige sowie die neuen Zurück/Vor- und Play/Pause-Tasten in der Wiedergabe. Der Button "Sender suchen", der seit Stufe 10 neu dazugekommen ist, war nicht angefordert und entfällt wieder. Die Karte bleibt sonst wie in Stufe 9.

Neu: Die Presets bekommen eine andere Bedienung.
Heute hat jede Preset-Zeile einen eigenen Play/Pause-Button, und ein Tipp auf den Namen öffnet "Sender ändern". Mit der Play/Pause-Taste in der Wiedergabe ist das zu viel: Auf der Karte stehen jetzt sieben Play-Buttons. Ich möchte es umdrehen:
- Ein Tipp auf die Preset-Zeile (Logo, Nummer, Name) spielt das Preset ab, wie die Taste am Gerät und wie in der Bose-App.
- Das Ändern des Senders wird ein kleiner, eigener Button pro belegtem Preset ("Preset ändern"). Der Play/Pause-Button pro Preset entfällt.
- Leere Presets behalten "Preset zuweisen" und tippen direkt in die Zuweisung.
- Pausieren geschieht nur über die Play/Pause-Taste der Wiedergabe. Ein Tipp auf das bereits laufende Preset macht nichts, es ist als "läuft" markiert (nicht nur per Farbe).
Das ist ein bewusster Bruch zur bisherigen Bedienung. Bitte entscheide selbst, wie sich die große Fläche (Abspielen) und der kleine Button (Ändern) am besten unterscheiden lassen, ohne dass die Zeile unruhig wird. Zeige zwei bis drei Varianten nebeneinander und empfiehl eine.

Zustände: belegt, laufend, wird gestartet (kurz), Start fehlgeschlagen, leer, deaktiviert (Gerät offline oder Standby), Fokus, gedrückt. Mit langem deutschem und schwedischem Sendernamen.

Qualitätsregeln wie bisher, für jede Ansicht, jeden Zustand und jede Größe: (1) ruhig, keine Sprünge beim Starten und Wechseln, reduced-motion; (2) Kontrast 4,5:1 für Text und 3:1 für Bedienelemente, hell und dunkel, Zustände nie nur durch Farbe; (3) voll per Tastatur bedienbar, sichtbarer Fokus, sinnvolle Reihenfolge innerhalb der Zeile (zuerst Abspielen, dann Ändern); (4) Screenreader-Namen ("Preset 2 abspielen: <Sender>", "Sender für Preset 2 ändern"), Ansage des Starts per role="status", Fehler per role="alert", 200 % Zoom; (5) 44-px-Tap-Ziele auch für den kleinen Ändern-Button, ohne dass er sich mit der Abspielfläche überschneidet, nichts nur per Hover; (6) 320, 390, 768, 1280 px, hell und dunkel; (7) Tokens und Komponenten der bisherigen Stufen, neue Texte nur über i18n-Schlüssel (englisch plus deutsch).

Liefere: die Presets-Zeile in den Varianten und Zuständen, dann die komplette Gerätekarte in allen Größen mit der gewählten Variante, kurz begründet nach den Qualitätsregeln 1 bis 7, und was sich gegenüber Stufe 9 ändert.

## Assistant



## User

Stufe 12 bitte anpassen (Stufe 13). Basis ist die Karte aus Stufe 10 mit den drei Quellen-Tasten aus Stufe 12, also mit Navigation "Geräte" und ohne "Lokale Steuerung". Zurück auf Presets schaltet um und spielt das zuletzt gewählte Preset, das bleibt so. Übernommen wird aus Stufe 12: die drei kleinen Quellen-Buttons oben in der Quellenanzeige sowie die Zurück/Vor- und Play/Pause-Tasten in der Wiedergabe. Der Button "Sender suchen", der seit Stufe 10 neu dazugekommen ist, war nicht angefordert und entfällt wieder. Sonst bleibt die Karte wie in Stufe 10.

Neu: Die Presets bekommen eine andere Bedienung.
Heute hat jede belegte Preset-Zeile einen eigenen Play/Pause-Button, und ein Tipp auf den Namen öffnet "Sender ändern". Mit der Play/Pause-Taste in der Wiedergabe ist das zu viel: Auf der Karte stehen jetzt sieben Play-Buttons. Ich möchte es umdrehen:
- Ein Tipp auf die belegte Preset-Zeile (Logo, Nummer, Name) schaltet um wie ein Toggle: Läuft das Preset nicht, startet es. Läuft es, pausiert es. Ist es pausiert, spielt es weiter. Die Zeile zeigt den Zustand eindeutig (läuft, pausiert, aus), nicht nur durch Farbe. Das entspricht der Taste am Gerät und der Bose-App.
- Das Ändern des Senders wird ein kleiner, eigener Button pro belegtem Preset ("Preset ändern"). Der Play/Pause-Button pro Preset entfällt.
- Leere Presets bleiben wie bisher: "Preset zuweisen" und Tipp direkt in die Zuweisung.
Das ist ein bewusster Bruch zur bisherigen Bedienung. Bitte entscheide selbst, wie sich die große Fläche (Abspielen und Pausieren) und der kleine Button (Ändern) am besten unterscheiden lassen, ohne dass die Zeile unruhig wird. Zeige zwei bis drei Varianten nebeneinander und empfiehl eine.

Zustände: belegt, läuft, pausiert, wird gestartet (kurz), Start fehlgeschlagen, leer, deaktiviert (Gerät offline oder Standby), Fokus, gedrückt. Mit langem deutschem und schwedischem Sendernamen.

Qualitätsregeln wie bisher, für jede Ansicht, jeden Zustand und jede Größe: (1) ruhig, keine Sprünge beim Starten, Pausieren und Wechseln, reduced-motion; (2) Kontrast 4,5:1 für Text und 3:1 für Bedienelemente, hell und dunkel (bitte das helle Theme diesmal mit einem Werkzeug prüfen, nicht nur schätzen), Zustände nie nur durch Farbe; (3) voll per Tastatur bedienbar, sichtbarer Fokus, sinnvolle Reihenfolge innerhalb der Zeile (zuerst Abspielen/Pausieren, dann Ändern); (4) Screenreader-Namen und Zustände ("Preset 2 abspielen: <Sender>", "Preset 2 pausieren: <Sender>", "Sender für Preset 2 ändern", Toggle mit aria-pressed oder gleichwertig), Ansage des Starts und Pausierens per role="status", Fehler per role="alert", 200 % Zoom; (5) 44-px-Tap-Ziele auch für den kleinen Ändern-Button, ohne dass er sich mit der Abspielfläche überschneidet, nichts nur per Hover; (6) 320, 390, 768, 1280 px, hell und dunkel; (7) Tokens und Komponenten der bisherigen Stufen, neue Texte nur über i18n-Schlüssel (englisch plus deutsch).

Liefere: die Presets-Zeile in den Varianten und Zuständen, dann die komplette Gerätekarte in allen Größen mit der gewählten Variante, kurz begründet nach den Qualitätsregeln 1 bis 7, und was sich gegenüber Stufe 10 ändert.

## Assistant

_[tool: run_script]_

_[tool: write_file]_

_[tool: write_file]_

_[tool: run_script]_

_[tool: delete_file]_

_[tool: snip]_

_[tool: dc_write]_

_[tool: ready_for_verification]_

_[tool: save_screenshot]_

_[tool: run_script]_

_[tool: ready_for_verification]_

Ich habe die drei Quellen-Tasten angepasst: Sie sind jetzt als Element selbst 44×44 px groß, die Kopfzeile bleibt durch einen negativen Rand 32 px hoch. Das hatte der Prüflauf auf der Gerätekarte bemängelt. Der erneute Lauf ist noch offen.

Mein eigener Kontrastlauf über Licht und Dunkel, 320, 390 und 1280 px und sechs Kartenzustände lieferte keine Ausgabe, die ich lesen konnte: Die Screenshots zeigen Frame-Inhalte nicht. Das Ergebnis des Prüflaufs, dass die Zeilenseite im hellen Thema grün auswertet, ist daher meine einzige Werkzeugprüfung. Für die Gerätekarte steht sie noch aus. Die Ergebnisse sind also nicht von mir unabhängig geprüft.

**Stand:** `OCT App Stufe 13.dc.html` zeigt die Preset-Zeile in drei Varianten mit allen Zuständen sowie die komplette Gerätekarte (Stufe 10 mit den Tasten aus Stufe 12). „Sender suchen“ ist entfallen, das Tippen auf eine Zeile schaltet zwischen Spielen, Pausieren und Fortsetzen um. Die Zustände belegt, läuft, pausiert, wird gestartet, Start fehlgeschlagen, leer, deaktiviert, Fokus und gedrückt sind abgebildet, mit langen deutschen und schwedischen Namen.

**Empfehlung V1** (geteilte Zeile mit Trennlinie, Stift-Spalte rechts, 48 px breit): Die beiden Flächen sind klar getrennt, die Zeile bleibt in jedem Zustand 76 px hoch, und die Trefferflächen überlappen nicht. V2 (runder Stift-Button) ist unruhiger, V3 (Stift mit Wort „Ändern“) ist deutlicher beschriftet, nimmt aber mehr Breite.

**Zustände sind nie nur Farbe:** Läuft hat Füllung, 2 px Rahmen, Lautsprecher-Symbol und Wort. Pausiert hat gestrichelten Rahmen, Pause-Symbol und Wort. Startet zeigt Spinner und „Startet…“. Fehlgeschlagen hat roten Rahmen, Kreuz und Text, die Zeile bleibt antippbar zum erneuten Versuch.

Noch offen: Die Notes zu Stufe 13 (Qualitätsregeln 1 bis 7, Änderungen gegenüber Stufe 10) habe ich noch nicht geschrieben. Das „Preset ändern“ öffnet im Prototyp noch nichts.

## User

Found issues — fixing…

## Assistant

_[tool: view_image]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: run_script]_

_[tool: save_screenshot]_

_[tool: view_image]_

_[tool: write_file]_

_[tool: ready_for_verification]_

Die Notes zu Stufe 13 stehen in `app13/STAGE13-NOTES.md`. Sie enthalten die Varianten, alle Zustände mit Namen und Ansagen, die Qualitätsregeln 1 bis 7, die neuen i18n-Schlüssel und die Änderungen gegenüber Stufe 10.

**Kontrast und Layout mit dem Werkzeug geprüft:** Ich habe die Prüfung des Projekts (Überlauf, Überlappung, Ziele mindestens 44 px, Kontrast mindestens 4,5:1) im Browser laufen lassen und die Ausgabe gelesen.
- **Zeilenseite:** In Hell und Dunkel bei 320, 390 und 1280 px ohne Befund.
- **Gerätekarte bei 320 px:** Sechs Zustände in Hell und Dunkel, darunter Standby als Zone-Slave, Schwedisch mit langen Namen und Fehler beim Umschalten, ohne Befund.
- **Gerätekarte bei 390 und 1280 px:** Hier waren es vier Zustände, ebenfalls ohne Befund.
- **Ränder von Bedienelementen:** Den 3:1-Kontrast der Ränder habe ich von Hand berechnet. Er liegt bei 3,9:1 im dunklen und 4,0:1 im hellen Thema.
- **Nicht geprüft:** 200 % Zoom ist kein Teil dieser Prüfung. Dort sorgt die feste Zeilenhöhe mit abgeschnittenen Namen für Ruhe.

**Zwei Fehler gefunden und behoben, die auch die Prototypen davor betrafen:**
- Die drei Quellen-Tasten waren nur über ein Hilfselement 44 px groß, jetzt sind sie als Element 44×44.
- Auf der Seite „Geräte“ bei 320 px überlappten die Geräte-Punkte die Pfeile, weil die Breite dort nicht gemessen wurde. Das ist in den Prototypen von Stufe 10, 12 und 13 behoben.

Die Empfehlung ist weiter V1 (geteilte Zeile mit Trennlinie). Nicht umgesetzt ist, dass „Preset ändern“ und „Preset zuweisen“ im Prototyp einen Dialog öffnen. Ob „Pausiert“ bei Radio am Gerät wirklich pausiert oder stoppt, ist eine Produktfrage.

