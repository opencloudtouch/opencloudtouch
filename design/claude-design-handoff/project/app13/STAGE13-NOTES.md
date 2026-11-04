# Stage 13: preset rows as toggles with their own "change" button

Prototype: `OCT App Stufe 13.dc.html` (frame `app13/stage13-frame.html`, `frame-pages.js`). New CSS: `PresetRow.css` (`.pr-*`, replaces `.pb`, `.pb-info`, `.pb-play`, `.pb-empty` on the card). Base is the stage 10 card (nav "Geräte", no "Lokale Steuerung") with the three source buttons from stage 12 (`SourceIndicator.css`, B only) and the track keys; "Sender suchen" is removed again. Reused unchanged: `DeviceCard.css` (stage 10), `theme-light.css`, `LocalControl.transport.css`, `NowPlaying.css`, `DeviceRemove.css`, `DeviceSwiper.css`.

## The row
One row, 76 px high in every state (the state line is always reserved, long names ellipsize; the full name is in `title` and in the accessible name). Left: **one large button** (number, logo, name, state line) that toggles: not playing, starts; playing, pauses; paused, resumes. Right: **one small button** "Preset ändern" (pencil). The old per-row Play/Pause button is gone; paused/playing is changed in the row or with the play key of the now-playing block (they stay in sync). Empty rows: "Preset zuweisen" with a plus, tap goes straight to the assignment.

### Three variants (page "Preset-Zeile, Varianten")
- **V1 split row (recommended):** the change button is a full-height 48 px column behind a hairline divider. Large area and small area are separate by shape, not only by size; the row stays one calm object; the targets cannot overlap.
- **V2 round button:** 36 px round button in a 52 px cell, no divider. Looks lighter, but the circle reads as an extra control in every row and makes six rows noisier.
- **V3 icon with word:** icon plus the visible word "Ändern" (12 px) in a 64 px column behind a hairline. Clearest for first-time users, but costs 16 px of name width and adds six repeated words.
Why V1: the same 44 px minimum, the least visual noise, and the divider is the one cue that explains "two different things" without a label.

### States (all in the page and on the card)
| State | How it looks (never colour alone) | Accessible name / announcement |
| --- | --- | --- |
| belegt | 1 px frame, number, logo, name | "Preset 2 abspielen: SWR3" |
| läuft | 2 px solid frame, tinted fill, speaker icon + "Läuft" | "Preset 2 pausieren: SWR3"; status "SWR3 spielt (Preset 2)" |
| pausiert | 2 px dashed frame, pause icon + "Pausiert" | "Preset 2 abspielen: SWR3"; status "SWR3 pausiert" |
| wird gestartet | 2 px frame, spinner + "Startet…", `aria-busy`, row inert for ~1 s | status "Startet…" |
| Start fehlgeschlagen | 2 px red frame, cross + "Start fehlgeschlagen", row stays tappable to retry | `role="alert"` "Preset 2 (SWR3) konnte nicht gestartet werden. Tippe erneut…" |
| leer | dashed frame, plus + "Preset zuweisen" | "Preset zuweisen 2" |
| deaktiviert (Standby, offline, Zone-Slave) | 60 % opacity, `aria-disabled`, both buttons | as above |
| Fokus | 2 px outline inside the button (`outline-offset: -4px`) | |
| gedrückt | tinted fill | |
Edit button name: "Sender für Preset 2 ändern". Tab order in the row: large button, then change button.

## Quality rules 1 to 7
1. **Calm.** Row height fixed at 76 px; the state line (18 px) is reserved in every state; starting, running, paused and failed only change frame, icon and word, never the size; the toggle never moves the grid. The only motion is the 160 ms background hover/press transition and the spinner; off under `prefers-reduced-motion` (spinner stays, it is state information). Changing source and switching device keep the earlier calm rules.
2. **Contrast.** I ran the project's own layout audit (overflow, overlap, targets at least 44 px, contrast at least 4.5:1, focusable scroll regions) in the browser on the finished prototype: the **preset rows page** (all three variants, all states, long names) at 320, 390 and 1280 px in **dark and light**, and the **device card** (running, failed start, starting, standby plus slave, Swedish with long names and failed switch, switching with "Mehr" menu open) at 320 px in dark and light and at 390 and 1280 px in dark and light for the main states: **all green** (no overflow, no overlap, targets at least 44 px, contrast at least 4.5:1). The audit checks text against its actual background; it does not measure the 3:1 of component borders, I computed those by hand: `--ui-control-border` is #8c8c8c on #242424 in dark (3.9:1) and #7a8494 on white in light (4.0:1).
3. **Keyboard.** Every row is two tab stops in the order large button, change button. Enter and Space toggle; after starting, pausing or a failed start the focus stays on that row's large button. Focus ring is 2 px, inside the button. No traps.
4. **Screen reader.** Names as in the table; each row is a button with a changing action label (no `aria-pressed` together with it); the six rows are a `role="group"` "Gespeicherte Sender"; start and pause are announced by one polite `role="status"`, a failed start by `role="alert"`; the visible state word and icon are `aria-hidden` (the label already says what the button does). Long names wrap nowhere, so 200 % zoom changes nothing; the accessible name always carries the full name.
5. **Targets.** Large area is the whole row minus the change button (at least 76 px high); the change button is 48 x 76 (V1), 52 x 76 cell (V2), 64 x 76 (V3); they never overlap, nothing depends on hover.
6. **Sizes.** 320, 390, 768, 1280 px, dark and light, with long German and Swedish names (data) and Swedish UI texts (button "Texte").
7. **Consistency.** Same tokens, same `pb-logo` avatar, same pressed/dashed/solid frame language as the source buttons of stage 12, the segments of stage 11 and the chips; texts only from keys.

## What changes against stage 10
- Presets: row is a toggle with state line, separate small "Preset ändern" button; the per-row Play/Pause and the "Sender ändern" tap on the name are gone; the row now shows which preset is running or paused.
- New: three small source buttons in the now-playing header (back to Presets switches and plays the last chosen preset); source section at the bottom removed.
- Removed: "Sender suchen" button above the presets (only "Vom Gerät laden" stays).
- Unchanged: header, zone badge, now playing, track keys, volume, remove footer, offline, standby, swiper, sticky bar.

## New i18n keys (en / de / sv in `app13/i18n-stage8-additions.json`)
`device.presetPlay` Play preset {{n}}: {{name}} / Preset {{n}} abspielen: {{name}}; `device.presetPause` Pause preset {{n}}: {{name}} / Preset {{n}} pausieren: {{name}}; `device.presetChange` Change station for preset {{n}} / Sender für Preset {{n}} ändern; `device.presetChangeShort` Change / Ändern; `device.prRunning` Playing / Läuft; `device.prPaused` Paused / Pausiert; `device.prStarting` Starting… / Startet…; `device.prFailed` Could not start / Start fehlgeschlagen; `device.presetStarted` {{name}} is playing (preset {{n}}) / {{name}} spielt (Preset {{n}}); `device.presetPausedAnn` {{name}} paused / {{name}} pausiert; `device.presetFailedAnn` Preset {{n}} ({{name}}) could not be started. Tap it to try again. / Preset {{n}} ({{name}}) konnte nicht gestartet werden. Tippe erneut, um es nochmal zu versuchen. Obsolete: `presets.changeStation`, `presets.playPreset`, `device.findStation`.

## Open points
1. "Preset ändern" and "Preset zuweisen" do not open the assignment dialog in the prototype (the dialog exists from stage 6b).
2. Pausing a radio stream is a product question for the device (stop versus pause); the UI shows "Pausiert".
3. The audit does not exercise the 200 % zoom; the layout there is checked by the fixed row height and ellipsis.
4. While fixing the audit I found two earlier issues that also affected the previous prototypes: the three source buttons were only 44 px through a pseudo element (now 44 x 44 elements with a negative margin), and the device dots were not measured on the "Geräte" page at 320 px, so they overlapped the arrows (fixed in the prototype frames of stages 10, 12 and 13).
