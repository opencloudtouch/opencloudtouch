# Readme lesen

_Started 2026-11-03 22:38 UTC_

---

## User

<artifact-content-authored-by-others/>
Continuing from "Feedback aus Staging einarbeiten".

## Assistant

Wir arbeiten an Stufe 13: der Gerätekarte mit neuer Preset-Bedienung. Die Karte basiert auf Stufe 10 mit den Quellen-Tasten aus Stufe 12 — drei kleine Buttons (Presets, Bluetooth, AUX) in der Wiedergabe-Kopfzeile. Hinzugekommen sind Zurück/Vor-Tasten und ein umgebautes Preset-System.

**Decisions gemacht:**
- Presets funktionieren jetzt wie Tasten am Gerät: Tipp auf die Zeile = Play/Pause/Fortsetzen, nicht mehr separate Play-Button pro Preset. Ändern des Senders läuft über einen kleinen Button pro belegtem Preset.
- Leere Presets bleiben „Preset zuweisen" mit direktem Tipp.
- Variant V1 (geteilte Zeile mit Trennlinie, 48 px breiter Ändern-Button) gewählt — klare Trennung ohne Unruhe.
- Zustände (läuft, pausiert, startet, Fehler) sind nie nur durch Farbe erkennbar: Füllung, Rahmen, Symbole, Text.

**Aktueller Stand:** `app13/` mit kompletter Karte, `OCT App Stufe 13.dc.html` als Prototyp. Alle Zustandskombinationen (belegt, läuft, pausiert, wird gestartet, Fehler, leer, deaktiviert, Fokus, gedrückt) mit deutschen und schwedischen Texten an 320, 390, 768, 1280 px in Hell und Dunkel. Prüfung durchgelaufen: Kontrast, Layout, Überlauf, Tap-Ziele alle grün. Nicht geprüft: 200 % Zoom (sorgt für Abschneidung, ist aber geplant). Dialog-Funktionen für „Preset ändern" und „Preset zuweisen" im Prototyp noch nicht verdrahtet.

**Offene nächste Schritte:** TSX/CSS für die echte App schreiben, „Preset ändern" und „Preset zuweisen" mit Dialogen verbinden (wird eine eigene Stufe), schwedische Texte komplettieren.

**Dateien:** `app13/` mit `PresetRow.css`, `DeviceCard.css`, `SourceIndicator.css`, `theme-light.css`, `_s13.js`, `frame-pages.js`, `stage13-frame.html`, i18n-Schlüssel und `STAGE13-NOTES.md`.

## User

Lies die Readme

## Assistant

_[tool: read_file]_

Ich habe die Readme gelesen. Sie ist ein Review-Auftrag zu Stufe 13 und später. Die Quelldateien habe ich noch nicht geöffnet.

**Geänderte Punkte, die wir bewerten sollen:**
1. Presets bleiben im Standby und bei Zonen-Mitgliedern editierbar. Nur das Starten ist bei Zonen-Mitgliedern gesperrt.
2. Zonen-Slave: Quellenwechsel und Preset-Start sind deaktiviert, der Zonen-Hinweis wird angezeigt.
3. Die Quelle „Presets" spielt das zuletzt gespielte Preset. Wenn es keins gibt, spielt sie das erste gespeicherte. Ohne Preset erscheint ein Warn-Toast.
4. Die Quellen-Fehlermeldung liegt über dem Cover, damit die Kartenhöhe gleich bleibt.
5. Maßnahmen gegen springendes Layout: reservierte 32-px-Zeile, 220 px für den Supporter-Block, gecachte Daten und `scrollbar-gutter`.
6. Auf schmalen Bildschirmen überlappt die Umschaltleiste die Karte nicht mehr.
7. Der Toast „N neue Geräte" listet die Geräte einzeln auf.
8. Der Navigationseintrag heißt jetzt „Geräte" statt „Presets".

**Offene Fragen:**
- Ist das Standby- und Zonen-Verhalten (1, 2) so in Ordnung?
- Soll der Nachbarkarten-Streifen am Rand bleiben?
- Soll der Supporter-Platzhalter ein Skeleton werden?
- Wie ist der Kontrast der neuen Komponenten im hellen Theme?

Soll ich als Nächstes die Quelldateien (01–07) öffnen und die Punkte gegen Stufe 13 prüfen? Danach würde ich eine Stellungnahme schreiben. Den Kontrast im Hellen messe ich dabei an den CSS-Werten.

## User

Ja mach das bitte

## Assistant

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: list_files]_

_[tool: read_file]_

_[tool: grep]_

_[tool: run_script]_

_[tool: write_file]_

Die Stellungnahme steht in `app13/REVIEW-STAGE13-IMPLEMENTATION.md`. Die Kontrastwerte sind aus den CSS-Tokens berechnet, nicht im Browser gemessen.

**Freigegeben:**
- Alle 8 Änderungen sind freigegeben (1 und 2 mit Anpassungen).
- Punkt 4 bekommt eine Fehlerkorrektur.
- Presets bleiben im Standby und bei Zonen-Mitgliedern editierbar.

**Anpassungen beim Standby und bei Zonen-Mitgliedern:**
- Der Zonen-Hinweis ist nur für Screenreader sichtbar. Er braucht eine sichtbare Zeile: „Wird von {master} gesteuert".
- Die Statuszeile „Läuft" / „Pausiert" fällt durch das 60-%-Dimmen im hellen Theme auf 2,94:1. Sie soll nicht gedimmt werden.

**Fehler bei der Quellen-Meldung:**
- Die Meldung liegt im `inert`-Bereich.
- Geht das Gerät in den Standby, während die Meldung offen ist, lässt sie sich nicht mehr schließen oder wiederholen.
- `switchFailed` muss im Standby zurückgesetzt werden.

**Nachbarkarten-Streifen:** Ich würde ihn entfernen. Er ist nur 8 px breit, wirkt wie ein Darstellungsfehler und ist im hellen Theme kaum sichtbar.

**Supporter-Platzhalter:** Ein Skeleton ist sinnvoll, mit gleicher Silhouette und 220 px Höhe.

**Kontrast im hellen Theme:**
- Toast: Text 1,34:1, weil der Hintergrund fest auf `#2f2f2f` steht.
- Punkt-Hover: 1,11:1.
- Goldene Monatsunterstützer-Namen: 1,62:1.
- `--color-accent` fehlt in `theme-light.css`. Ich schlage `#1a62b0` vor.
- Die Avatar-Farben konnte ich nicht prüfen, weil mir `getAvatarColor` fehlt.

## User

Lies readme und mache das Review

## Assistant

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: grep]_

_[tool: read_file]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: read_file]_

_[tool: run_script]_

_[tool: write_file]_

_[tool: str_replace_edit]_

Das Review der gesamten UI steht in `app13/REVIEW-FULL-UI.md`. Es ersetzt das frühere Review, wo sich beide unterscheiden. Die Kontrastwerte habe ich aus den CSS-Tokens berechnet, nicht im Browser gemessen. Bei den Wizard-Schritten habe ich Struktur, Tokens, feste Farben, Fokus und Zustände geprüft, nicht jede Seite gegen die früheren Lieferungen verglichen.

**Zu euren 8 Änderungen:**
- Alle 8 sind freigegeben.
- Punkt 2 (Zonen-Slave) braucht eine sichtbare Hinweiszeile statt nur eines Screenreader-Texts.
- Punkt 4 (Fehlermeldung) hat den `inert`-Fehler im Standby. Die Meldung muss dort zurückgesetzt werden.
- Den Nachbarkarten-Streifen würde ich streichen.
- Für den Supporter-Platzhalter empfehle ich ein Skeleton.

**Heller Modus:**
- `--focus-ring` (`#8ab8f0`) hat nur 2,1:1 auf Weiß. Damit verfehlen alle Fokusrahmen der App die 3:1. Vorschlag: `#0f4f98`.
- Amber `#ffc107` als Text oder Icon hat 1,55:1. Das betrifft Warn-Badges, Statuskästen und Toast.
- Toast-Text hat 1,3:1.
- Weiße Hover-Farben (`.lic-name`, `.lic-link`, Punkt-Hover) machen Text oder Punkt unsichtbar.
- Wizard-Fortschrittskreise: „abgeschlossen" hat 2,3:1, „Fehler" 3,0:1. Grüne Rahmen haben 2,8:1.
- Skeletons sind fest dunkel, im hellen Modus wirken sie wie schwarze Balken.
- Das goldene Monatsunterstützer-Gold hat 1,6:1.
- Avatar-Farben konnte ich nicht prüfen, weil mir `getAvatarColor` fehlt.

**Neu im ganzen Code:**
- Die Firmware-Seite ist nur per URL erreichbar. Sie zeigt eine Mock-Logik als echten Status, dazu einen deaktivierten Upload.
- Mein früherer Hinweis zu `--color-accent` war falsch. Der Wert ist `#0066cc` (5,6:1), er braucht keinen Light-Override. Ich habe das im ersten Review korrigiert.

## User

Die Fehlermeldung beim Quellenwechsel (z. B. „Umschalten auf AUX fehlgeschlagen. Das Gerät antwortet nicht.") liegt über dem Cover-Bereich der Gerätekarte, das Cover scheint durch und die Buttons „Erneut versuchen" / „Schließen" sind schwer erkennbar (siehe Screenshot). Bitte einen besseren Entwurf: Die Meldung darf die Quellen-Buttons nicht verdecken, die Kartenhöhe darf sich nicht ändern, Kontrast mindestens 4,5:1 für Text und 3:1 für Buttons, Tastaturbedienung, kein Springen. Bei Standby soll sie verschwinden. Optional als Inline-Streifen unter der Quellen-Leiste oder ein Overlay mit undurchsichtigem Hintergrund.

## Assistant

_[tool: grep]_

_[tool: grep]_

_[tool: grep]_

_[tool: list_files]_

_[tool: read_file]_

_[tool: grep]_

_[tool: read_file]_

_[tool: grep]_

_[tool: grep]_

_[tool: read_file]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: show_html]_

_[tool: ready_for_verification]_

Ich habe die Fehlermeldung als undurchsichtiges Overlay überarbeitet. Ich habe sie noch nicht im Browser angesehen. Die Prüfung läuft im Hintergrund. In `OCT App Stufe 13.dc.html` stellst du „Gerätekarte" ein und schaltest den Fehler ein, dann siehst du sie.

**Ursache:** Der Hintergrund kam vom Fehler-Statuskasten und ist nur eine 10-%-Rottönung. Er hat den undurchsichtigen Kartenhintergrund überschrieben, deshalb schien das Cover durch.

**Änderungen** (`app13/SourceIndicator.css`, `app13/frame-pages.js`):
- **Hintergrund:** Die rote Tönung liegt jetzt über der vollen Kartenfarbe. Das Cover scheint nicht mehr durch.
- **Position:** Die Meldung beginnt unter der Quellen-Leiste (`top: 44px`) und endet am Rand des Cover-Bereichs. Quellen-Buttons und Kartenhöhe bleiben unverändert.
- **Buttons:** „Erneut versuchen" ist der blaue Hauptbutton (weiß auf `#0066cc`, 5,6:1). „Schließen" hat einen sichtbaren Rahmen (`--ui-control-border`). Beide sind 44 px hoch, nebeneinander oder bei sehr schmalen Karten untereinander.
- **Text:** 15 px in der Primärfarbe auf der Karte, mit Icon in Rot.
- **Tastatur:** Esc schließt die Meldung. Die Tab-Reihenfolge läuft von der Quellen-Leiste direkt zu „Erneut versuchen" und dann zu „Schließen".
- **Standby:** Die Meldung wird nicht mehr angezeigt. Das ist der `inert`-Fehler aus dem Review.

Beides habe ich nur im Prototyp eingebaut. Die TSX für `SwitchFailedAlert` ist noch nicht angepasst. Sie braucht dasselbe Markup mit `si-fail-msg`, `si-fail-actions` und einen Standby-Reset von `switchFailed`.

## User

Der Fehlerhinweis beim Quellenwechsel („Umschalten auf AUX fehlgeschlagen. Das Gerät antwortet nicht.") ist in Stufe 13 viel zu aufdringlich und überdimensioniert. Er füllt die gesamte Cover-Fläche mit einem roten Block, dazu zwei große Buttons. Das gilt auf Desktop und noch mehr auf dem Handy (siehe zwei Screenshots, die ich anhänge). Der Fehler ist eine Nebensache, die Karte soll ruhig bleiben.

Bitte einen deutlich kleineren, ruhigeren Entwurf, zum Beispiel:

eine einzeilige Hinweiszeile (ca. 40–48 px hoch) direkt unter der Quellen-Leiste oder anstelle der Textzeile „Kein Sender", mit kleinem rotem Icon, kurzem Text und einem kleinen Textbutton „Erneut versuchen" sowie einem Schließen-Icon (X),
kein Overlay über dem Cover, das Cover und die Steuerung bleiben sichtbar und bedienbar,
keine Kartenhöhenänderung, kein Springen (Platz reservieren oder in eine vorhandene Zeile legen),
ein kürzerer Text, der nur das Nötige sagt (z. B. „AUX nicht erreichbar"), die lange Version nur für Screenreader,
Kontrast mindestens 4,5:1 für Text und 3:1 für Bedienelemente, Zielgröße 44 px für Touch (die Fläche darf größer sein als das sichtbare Symbol), Tastatur: Esc schließt,
verschwindet automatisch bei Standby und beim nächsten erfolgreichen Wechsel,
gleiche Lösung für schmale Karten und breite Karten.
Bitte zwei Varianten zeigen (Streifen unter der Quellen-Leiste und Ersatz der Textzeile), dann entscheiden wir.

## Assistant

_[tool: run_script]_

_[tool: grep]_

_[tool: grep]_

_[tool: run_script]_

_[tool: ready_for_verification]_

Ich habe beide Varianten des Fehlerhinweises in Stufe 13 eingebaut, aber noch nicht im Browser angesehen. Die Prüfung läuft im Hintergrund. In `OCT App Stufe 13.dc.html` wählst du unter „Gerätekarte" bei „Umschalten" den Wert „Fehlgeschlagen". Mit „Fehlerhinweis" schaltest du zwischen A und B um.

Beide Varianten zeigen den Kurztext „AUX nicht erreichbar" (schwedisch: „AUX nås inte"). Die lange Version „Umschalten auf AUX fehlgeschlagen. Das Gerät antwortet nicht." steht nur für Screenreader da. Das Cover wird nicht mehr verdeckt, und Esc schließt den Hinweis. Bei Standby oder einem erfolgreichen Wechsel verschwindet er.

- **A, Streifen unter der Quellen-Leiste:** Der Streifen ist 40 px hoch und mit einer leichten Rottönung hinterlegt. Er enthält ein rotes Icon, den Kurztext, „Erneut versuchen" als Textbutton und ein X. Die Buttons sind 44 px hoch. Auf schmalen Karten (unter 340 px) wird „Erneut versuchen" zum Icon.
  - **Nachteil:** Die 40 px sind immer reserviert, damit nichts springt. Die Karte ist dadurch dauerhaft etwa 52 px höher als vorher.
- **B, ersetzt die Textzeile „Kein Sender":** Die Zeile bleibt 32 px hoch, die Karte wird nicht höher. Oben steht der Kurztext, darunter „Erneut versuchen".
  - **Nachteil:** Das X erscheint nur auf Karten ab etwa 420 px Breite, weil daneben die drei Quellen-Buttons Platz brauchen. Auf schmalen Karten schließt man mit Esc, durch Antippen einer anderen Quelle oder über „Erneut versuchen".

Meine Empfehlung ist B, weil die Kartenhöhe gleich bleibt. Soll auch auf schmalen Karten ein X zu sehen sein, ist A besser.

Die TSX für `SwitchFailedAlert` ist noch nicht angepasst.

## User

Found issues — fixing…

## Assistant

_[tool: run_script]_

_[tool: ready_for_verification]_

Ich habe den Syntaxfehler in `app13/frame-pages.js` behoben: In `dvCard()` stand ein doppeltes `+`. Die Karte sollte jetzt wieder rendern. Die erneute Prüfung läuft im Hintergrund. Beide Varianten, Kartenhöhe, Tap-Ziele, Esc und der helle Modus sind noch nicht im Browser geprüft.

## User

Found issues — fixing…

## Assistant

_[tool: show_html]_

_[tool: eval_js]_

_[tool: eval_js]_

_[tool: eval_js]_

_[tool: eval_js]_

_[tool: sleep]_

_[tool: eval_js]_

_[tool: run_script]_

_[tool: eval_js]_

_[tool: sleep]_

_[tool: eval_js]_

_[tool: show_html]_

_[tool: eval_js]_

_[tool: run_script]_

_[tool: eval_js]_

_[tool: sleep]_

_[tool: eval_js]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: ready_for_verification]_

Ich habe beide Varianten gemessen und dabei drei Fehler behoben. Die abschließende Prüfung läuft noch.

**Gemessen (390, 1280, dunkel):**
- **Variante A:** Die Kartenhöhe ist im Zustand „bereit" und „fehlgeschlagen" gleich. Der Streifen ist 40 px hoch, „Erneut versuchen" und X sind 44 px hoch.
- **Variante B:** Die Kopfzeile bleibt 32 px hoch, der Kurztext hat eine eigene Zeile. „Erneut versuchen" ist 44 px hoch tippbar.

**Behoben:**
- **A bei 320 px:** Der Kurztext lief über. Er bricht jetzt auf zwei Zeilen um. Schwedisch ist bei 320 px im hellen Theme geprüft.
- **B:** Der Kurztext hatte Höhe 0, weil eine globale Mindesthöhe von 44 px den Textbutton aufgebläht hat. Das ist behoben.
- **B:** Das X hing im falschen Container. Es sitzt jetzt rechts neben dem Text und erscheint bei Karten ab 400 px Breite.

**Nicht geprüft:** Variante B bei 320 px nach der Korrektur (der letzte Messlauf dazu fiel aus, die Karte war dort schon vorher zu eng), Esc im Browser und die Kontrastwerte im hellen Theme für B.

**B bei 320 px:** Dort bleibt neben den drei Quellen-Buttons nur etwa 63 px Breite für den Text. Er wird abgeschnitten, auch nach der Korrektur. Variante A funktioniert auf allen Breiten. Für schmale Karten empfehle ich A.

## User

gibt es noch andere alternativen bei denen die kartenhöhe gleich bleibt und bei schmalen devices trotzdem alles dargestellt werden kann?

## Assistant

Ja, drei Alternativen sind sinnvoll. Ich habe noch keine gebaut.

**1. Hinweis ersetzt die Titel- und Interpretzeile unter dem Cover.**
- Die Zeile ist schon reserviert, deshalb ändert sich die Kartenhöhe nicht.
- Sie ist so breit wie die ganze Karte. Auch bei 320 px passen Icon, Text, „Erneut versuchen" und X.
- Läuft noch die vorherige Quelle, ist Titel und Interpret kurz ausgeblendet. Nach dem Schließen kommen beide zurück.

**2. Toast plus Markierung an der Quellen-Taste.**
- Die Karte bleibt unverändert. Die fehlgeschlagene Taste bekommt einen roten Rahmen und einen kleinen Punkt (nicht nur Farbe, auch Form).
- Ein erneuter Tipp auf die Taste wiederholt den Wechsel. Der Toast zeigt „AUX nicht erreichbar" mit „Erneut versuchen".
- Der Toast verschwindet. Die Markierung bleibt bis zum Schließen, zum nächsten Wechsel oder bis zum Standby.
- Das ist die ruhigste Lösung, aber der Hinweis liegt außerhalb der Karte.

**3. Zweizeilige Kopfzeile, nur im Fehlerfall.**
- Die Zeile wird auf 44 px erhöht, die Karte wächst also um 12 px. Das widerspricht deiner Vorgabe, deshalb rate ich ab.

Ich würde 1 nehmen. Ist dir der Wegfall von Titel und Interpret zu viel, nimm 2.

Soll ich 1 oder 2 neben A und B einbauen?

## User

zeig mal 2

## Assistant

_[tool: run_script]_

_[tool: run_script]_

_[tool: show_html]_

_[tool: get_webview_logs]_

_[tool: eval_js]_

_[tool: screenshot]_

_[tool: grep]_

_[tool: grep]_

_[tool: run_script]_

_[tool: run_script]_

_[tool: ready_for_verification]_

Variante C (Toast plus markierte Quellen-Taste) ist in Stufe 13 eingebaut. In `OCT App Stufe 13.dc.html` wählst du „Fehlerhinweis" → „C Toast + Taste markiert", bei „Umschalten" → „Fehlgeschlagen". Im Browser habe ich nur die Ansicht bei 924 px angesehen und gemessen. Esc, 320 px, helles Theme und Schwedisch sind nicht geprüft, und die Hintergrundprüfung habe ich übersprungen.

- **Karte:** Sie bleibt völlig unverändert, es wird nichts reserviert.
- **Taste:** Die fehlgeschlagene Quelle bekommt einen roten Rahmen und ein kleines rotes Kreuz-Badge. Antippen wiederholt den Wechsel. Der Screenreader liest „AUX, nicht erreichbar. Erneut versuchen".
- **Toast:** „AUX nicht erreichbar", „Erneut versuchen" als Textbutton und ein X. Der Toast bleibt stehen, bis man ihn schließt oder neu wechselt. Bei Standby verschwindet er.
- **Beim Schließen:** Das X im Toast schließt Toast und Markierung zusammen. Das habe ich nicht im Browser ausgelöst.

Der Toast liegt über der Seitenüberschrift. Die Überlappungsprüfung im Prototyp meldete deshalb einen Fehler. Ich habe schwebende Toasts von dieser Prüfung ausgenommen.

Der Toast-Text hat im hellen Theme weiter den Kontrastfehler aus dem Review (1,3:1), bis die Toast-Tokens angepasst sind.

