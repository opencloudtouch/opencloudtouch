# Stage 5: Grundlagen, Shell, Willkommen/404/Fehler, Presets, Stationssuche

Prototyp: `OCT App Stufe 5.dc.html` (Breite 320/375/414/768/1280, Zustandsauswahl je Seite, Audit-Chip: Overflow, Überlappung, Tippziele ≥44 px, Kontrast ≥4,5:1, nicht fokussierbare Scroll-Bereiche).
Alles liegt in `app/`. `Icon.tsx` gehört nach `components/Icon.tsx` (Obermenge der Wizard-Version, bestehende Pfade unverändert; `wizard/Icon.tsx` kann `export * from "../Icon"` werden).

## Dateien
Neu: `ui-base.css`, `Modal.tsx` + `Modal.css`, `app-shell.css`, `Icon.tsx`.
Komponenten (Drop-in, gleiche Namen/Props): `App.tsx`, `Navigation`, `LanguageSelector`, `Toast`, `ConfirmDialog`, `ErrorBoundary`, `LoadingSkeleton`, `EmptyState`, `ManualIPModal`, `NotFound` (pages/), `DeviceOfflineBanner`, `RadioPresets` (pages/), `DeviceSwiper`, `NowPlaying`, `PresetButton`, `VolumeSlider`, `DeviceNameEditor`, `SetupBadge`, `StatusBadge`, `RadioSearch`, `StationDetail`, je mit eigener CSS.
Import-Reihenfolge: `index.css`, dann `ui-base.css` (in `App.tsx` importiert, ersetzt `App.css`).

Präfixe: `ui-` Primitive, `wz-` geteilt mit Wizard, `dlg-` Dialoge, `nav-`, `lang-`, `toast-`, `eb-`, `es-`, `mip-`, `nf-`, `dob-`, `sk-`, `rp-`, `ds-`, `np-`, `pb-`, `vs-`, `dne-`, `sb-`, `rs-`, `sd-`.

### Alte Dateien, die entfallen
`App.css`, `Navigation.css`, `LanguageSelector.css`, `Toast.css`, `ConfirmDialog.css`, `ErrorBoundary.css`, `LoadingSkeleton.css`, `EmptyState.css`, `NotFound.css`, `DeviceOfflineBanner.css`, `RadioPresets.css`, `DeviceSwiper.css`, `NowPlaying.css`, `PresetButton.css`, `VolumeSlider.css`, `DeviceNameEditor.css`, `SetupBadge.css`, `StatusBadge.css` (Komponente importiert keine CSS mehr), `RadioSearch.css`, `StationDetail.css`. Modal-Regeln aus der alten `ManualIPModal`/`EmptyState`-CSS entfallen mit ihnen.

## App.tsx (Änderungen)
Nur Markup: Lade- und Fehlerbildschirm in `<main>` mit `app-state`-Klassen (Fehler: `h1` statt `h2`, `role="alert"`), Emoji durch Icons ersetzt, Imports `ui-base.css`/`app-shell.css`/`Icon`. Skip-Link, Header, `<main id="main-content">` und Routing unverändert. `.app-main` bleibt der Scroll-Container (Header ist eine feste 64-px-Leiste).
Willkommen-Route: `Navigate to="/"` wie bisher.

## Überschriftenstruktur
Presets: h1 Seitentitel, h2 Gerätename (der Umbenennen-Button sitzt jetzt in einem `h2`), h2 „Gespeicherte Sender“, h2 „Hinweise“ (vorher h3). Suchdialog: h2 Titel, h3 Sendername im Detail. Willkommen: h1, h2 je Schritt. 404 und ErrorBoundary: Titel ist h1 (die „404“ ist `aria-hidden`).

## (a) Neue i18n-Keys (DE + EN)
Vollständig in `app/i18n-stage5-additions.json`. Neu:
- `presets.unknownDevice` / `unknownModel` / `unknownIp`: „Unbekanntes Gerät“ / „Unbekanntes Modell“ / „Unbekannte IP“ — Unknown device / Unknown model / Unknown IP
- `presets.searchHint`: „Mindestens 2 Zeichen eingeben, um zu suchen.“ — Enter at least 2 characters to search.
- `presets.manualInvalidUrl`: „Bitte eine gültige HTTP- oder HTTPS-Adresse eingeben.“ — Please enter a valid HTTP or HTTPS address.
- `presets.searchTypeGroup` „Suchen nach“ / Search by; `presets.providerGroup` „Quelle“ / Source; `presets.searchResults` „Suchergebnisse“ / Search results
- `player.source.bluetooth|radio|aux|airplay|dlna|tv|spotify|deezer|pandora|amazon|storedMusic` (DE: u. a. „Mediathek“, EN: „Media library“)
- `stationDetail.codec|bitrate|homepage`
- `manualIpModal.placeholder` (mehrzeilig) und `manualIpModal.saved` („IP-Adressen gespeichert!“ / „IP addresses saved!“)
- `discovery.deviceSaved`: „Gespeichert“ / Saved

Geänderte bestehende Texte (Emoji entfernt): `presets.infoItem3` (kein „►“ mehr), `presets.infoItem5` (kein „⚙️“ mehr, verweist auf das Status-Symbol). `setupBadge.*` und `statusBadge.*` kommen in Ihrer hochgeladenen JSON nicht vor; ich gehe davon aus, dass sie in der App existieren. Mein Wortlaut im Prototyp steht in der Additions-Datei, bitte abgleichen.
Schon vorhanden und jetzt genutzt: `a11y.selectLanguage`, `a11y.switchToDevice`, `a11y.deviceSelection`, `player.muteOn|muteOff`, `common.loading`.

## (b) Logikabweichungen
Alles additiv oder rein visuell; Props, Hooks, Effekte, API-Aufrufe, Timer und `t()`-Keys bleiben.
1. `Modal`: neue Komponente. `ConfirmDialog` bekommt die optionale Prop `destructive` (roter Bestätigen-Button); `RadioPresets` setzt sie für „Preset löschen“.
2. `LanguageSelector`: Fokus wandert beim Öffnen in die Liste, Pfeiltasten/Home/End navigieren, Fokus kehrt zum Button zurück. Neuer Effekt und `onKeyDown`.
3. `VolumeSlider`: Home/End, `preventDefault` bei Pfeiltasten, `aria-pressed` am Mute-Button, Wertanzeige (`aria-hidden`). `MUTED_COLOR` von `rgba(255,255,255,.35)` auf `#8c8c8c` (Kontrast). `aria-label` jetzt aus `player.muteOn|muteOff` statt hartem „Mute“/„Unmute“.
4. `DeviceNameEditor`: Berechnung der Icon-Breite nutzt `size * 0.65` statt `measureText("✏️")` (das Icon ist jetzt ein SVG).
5. `RadioPresets`: `aria-pressed`/`aria-busy` am Power-Button, `role="alert"` an beiden Fehlerbannern. Das Offline-Banner animiert nur noch `y`, nicht `opacity`.
6. `RadioSearch`: sichtbare Titelzeile (`presets.searchTitle`), `data-autofocus` für den ersten Fokus, `aria-invalid` plus Fehlertext bei ungültiger Stream-/Logo-URL (nutzt vorhandenes `isValidHttpUrl`), Hinweis bei leerer Suche.
7. `DeviceSwiper`: Punkte sind eine Gruppe aus Buttons mit `aria-current` statt `role="tablist"`/`tab`. Verhalten unverändert.
8. `NowPlaying`: Quellen-Badge ist für Screenreader versteckt, wenn der Text schon im Header steht; sonst `role="img"` mit Label. `getSourceBadge`/`getSourceLabel` bekommen `t` als Parameter.
9. **Vorschlag, nicht umgesetzt:** „Gerät entfernen“ löscht weiter sofort. Bestätigung (im Prototyp unter Bestätigungen → Gerät entfernen): in `RadioPresets` `const [removingDevice, setRemovingDevice] = useState(false)`, Button ruft `setRemovingDevice(true)`, dazu `<ConfirmDialog destructive open={removingDevice} … onConfirm={() => { setRemovingDevice(false); deleteCurrentDevice(); }} onCancel={() => setRemovingDevice(false)} />`. Es braucht noch Keys für Titel/Text (z. B. `presets.confirmRemoveDeviceTitle|Message`).

## (c) Tests anpassen
- jsdom kennt `HTMLDialogElement.showModal` nicht überall: `Modal` fällt auf das `open`-Attribut zurück; die Dialogtests laufen damit, Fokusfalle und Inertness sind nur im Browser/Cypress prüfbar.
- `ManualIPModal`: Erfolgstext kommt aus `manualIpModal.saved` („IP addresses saved!“ in EN); der Test sucht noch „IP-Adressen gespeichert!“. Das Platzhalter-Beispiel ist jetzt ein Key. `data-test="modal-overlay|modal-content|modal-title"` bleiben, `modal-content` ist das Panel.
- `ConfirmDialog`: `alertdialog`-Rolle liegt am `<dialog>`; `aria-labelledby`/`-describedby` unverändert; Overlay-Klick ruft `onCancel`, Klick auf den Dialog nicht. Klassen `confirm-dialog-*` entfallen (Tests nutzen testids).
- `Toast`: Klassen `toast`, `toast-<typ>`, `toast-visible` bleiben.
- `DeviceSwiper`: `getAllByRole("tab")` wird zu Buttons mit Namen „Zu … wechseln“; Zustand über `aria-current="true"` statt `aria-selected`.
- `VolumeSlider`: Mute-Button-Name ist jetzt `player.muteOn|muteOff` (nicht „Mute“/„Unmute“).
- `NotFound`: „404“ ist kein `h1` mehr (der Titel „Seite nicht gefunden“ ist es); `getByRole("heading", { level: 2 })` entfällt.
- `ErrorBoundary`: Titel ist `h1`; Details-`pre` haben `tabIndex=0`.
- `SetupBadge`: Klassen `sb sb--<status>` statt `setup-badge badge-*`; Icon sitzt in `.sb-icon`; `failed` hat jetzt eigenes Icon und eigene Klasse (vorher `badge-unconfigured`). `StatusBadge`: Klassen `ui-badge ui-badge--<variante>`, Icon ohne Label hat `role="img"` plus Name.
- `PresetButton`: Klassen `pb`, `pb-info`, `pb-play`, `pb-empty`; testids unverändert. `RadioPresets`: Power-Button `rp-power rp-power--on|off` (vorher `power-header-btn on|off`), Sync-Button ohne `sync-icon`-Glyphe, Gerätename ist `h2` > `button`.
- `DeviceNameEditor`: `device-name-editor` umgibt jetzt auch einen `h2`; Anzeigezustand ist `h2` > `button[data-test=device-name]`.
- Emoji-Selektoren (z. B. Text „⏻“, „✕“, „🔄“) entfallen, Elemente per Rolle/Name wählen.
- `EmptyState`: Schritte sind eine `ol`; der Fortschritts-Check hat `role="img"` mit „Gespeichert“.

## (d) Offene Punkte
1. `getAvatarColor` (utils/stationAvatar): Initialen sind weiß. Damit der Kontrast sicher ≥4,5:1 hält, sollte die Funktion Farben mit L ≤ 35 % liefern (z. B. `hsl(h 45% 32%)`, wie im Prototyp). Datei war nicht Teil der Lieferung.
2. Toasts: `ToastContext` hält genau einen Toast. Ein Toast, der bei offenem Dialog erscheint, liegt unter dem Dialog-Backdrop und ist inert. Im aktuellen Ablauf schließt der Dialog vorher.
3. Fokus zurück an den Auslöser: Wird der Auslöser entfernt (z. B. leeres Preset wird belegt), landet der Fokus auf `<main>`.
4. Tab-Reihenfolge Swiper auf Phones: Pfeile stehen im DOM vor der Karte, optisch darunter (wie bisher).
5. Punkte im Swiper sind 44 px breit, bei 12 Geräten ergibt das auf 320 px zwei Zeilen.
6. Flaggen im Prototyp sind ein Platzhalter; in der App lädt `flag-icons` weiterhin die echten.
7. Die Ergebnisliste und die manuellen Felder im Suchdialog sind `tabindex=0`-Regionen (Scroll-Bereiche), das sind zwei zusätzliche Tab-Stopps.
8. Chrome kann bei zweimaligem Esc ohne Interaktion `<dialog>` ohne `cancel`-Event schließen; da der Zustand in React liegt, empfehle ich im Cypress-Test beide Wege zu prüfen.
9. `StationDetail`: `new URL(station.homepage)` kann bei fehlerhafter URL werfen (unverändert, nur notiert).

## (e) Regeln in `wizard-base.css`, die später entfallen können
Sobald `ui-base.css` global geladen ist (1:1-Kopien): der gesamte Block `.btn`, `.btn-primary|secondary|outline|ghost`, `.btn svg, .wz-icon svg`, `.spinner-small, .spinner`, `@keyframes spin`; `.wz-status` mit Varianten, `.wz-icon`, `.wz-status-body|title|text`, `.wz-status-body > p`; `.wz-spinner`; `.wz-progress`, `.wz-progress-bar`, `--indeterminate`, `@keyframes wz-indeterminate` (samt Reduced-Motion-Regeln); `.inline-link-button`. `.wz-card` und `.mono/.device-ip/.wz-mono` bleiben (nicht in ui-base).
Achtung: `.device-ip` in `wizard-base.css` (Wizard-Header) ist weiter global; die Presets-Seite nutzt jetzt `rp-device-ip`, die alte `.device-ip { opacity: .65 }` ist mit `RadioPresets.css` weg.
