# Stage 10: the device card (page "Geräte")

Prototype: `OCT App Stufe 10.dc.html` (frame `app10/stage10-frame.html`, markup `frame-pages.js`). New CSS: `DeviceCard.css` (replaces the `.rp` page/card rules and the `.lc` card rules), `theme-light.css` (draft). Reused unchanged: `RadioPresets.css` header rules (`.rp-card-head`, `.rp-power`, `.rp-device-*`), `LocalControl.css` (`.lc-key`, `.lc-zone`), `app9/LocalControl.transport.css`, `DeviceSwiper.css`, `DeviceSwiper.sticky.css`, `DeviceRemove.css`, `NowPlaying.css`, `VolumeSlider`, `PresetButton`.
The prototype uses the brief's name "Stufe 9"; the earlier "Stufe 9" in this project is the transport-key patch (`app9/`), which this stage replaces on the card.

## Order of the card (top to bottom)
1. Header: power, name (editable), model, IP, setup badge; zone badge under it (Master / Mitglied).
2. Now playing (cover or source tile, title, artist, source badge). Fixed height.
3. Track keys: always one 76 px row.
4. Volume and mute: the one `VolumeSlider` (mute button, slider, value). The "Stumm" quick action of Local control is gone.
5. Presets 1 to 6 (unchanged slots, empty state, playing preset highlighted) with "Sender suchen" and "Vom Gerät laden".
6. Source: one collapsed row.
7. "Gerät entfernen" footer (as in stage 8).

Why this order: what plays, how to control it, how loud, then what else to play (presets), then the rarely used change of input. Source sits last because it is used least and cannot be chosen for most sources anyway.

**Phones (320, 390):** one column; preset slots keep their current size, one per row (two per row would make them smaller than today). The card is about 1450 px tall; what keeps it manageable is the order (what plays and its keys on the first screen), the sticky device bar and the collapsed source row. If this is still too long, the next step would be to collapse the presets below the first screen, not to shrink the slots. Always visible: 1 to 5 and 7. Collapsed: source (a 56 px row showing the current source). The card is longer than before (presets are now inside it); the sticky device bar from stage 6d keeps the device name in view while scrolling.
**768:** one column, card capped at 560 px, centred (as before).
**1024 and up:** two columns inside the same card (left 400 px: playing, keys, volume; right: presets, source). Source is expanded by default from 1024 px because there is room.

## Track keys
- Bluetooth, AirPlay, DLNA, Spotify (and Deezer, Pandora, Amazon, same flag `tk`): Zurück, Play/Pause, Vor.
- Radio (preset or search), TuneIn: only Play/Pause, centred.
- AUX, TV: no keys, the row shows one line "Die Wiedergabe wird am angeschlossenen Gerät gesteuert." (no jump).
- Standby: one disabled Play key. Offline: no keys.
The row is 76 px high in every variant, so the card does not change height when the source changes. In the previous patch (stage 9) disabled keys stayed visible; here they are removed as you specified.

## Source
- **Current source is always marked:** the row shows the source tile (same `.ui-source` badge as in now playing) and "Aktuell: Spotify". This also works for sources that cannot be chosen (Spotify, DLNA, Radio, TV): in the expanded panel nothing is pressed and one line explains why ("Spotify wurde in der App gestartet…", "Radio startet über die Presets…").
- **Choice:** `.ui-chips` group (`role="group"`, label "Quelle wählen"), chips with `aria-pressed` (the existing chip look with check mark): Bluetooth, AUX, AirPlay only if the device supports it (2 or 3 chips).
- **Switching (1 to 3 s):** the row opens automatically, the tapped chip shows a spinner and `aria-busy`, all chips are disabled, the row says "Wechsle zu AUX…". Now playing stays as it is until the device answers.
- **Failed:** the panel stays open with an error alert ("Umschalten auf AUX fehlgeschlagen. Das Gerät antwortet nicht.", button "Erneut versuchen"), the row still shows the previous source.
- **Standby:** everything under the header is dimmed (opacity .6) and carries the `inert` attribute on its wrappers (no focus, no tab stop, hidden from assistive technology as active controls) (now playing becomes the placeholder "Gerät im Standby. Einschalten, um Musik zu hören."), chips are disabled, hint "Zum Umschalten das Gerät einschalten.". Power is the only active control. Presets are inert as well, one rule for the whole card.
- **Announcements:** one `role="status"` region sits next to the row (outside the collapsible panel): switching, switched, failed. The failure also has its own `role="alert"`.

## Navigation and title
- Nav entry "Presets" becomes **"Geräte" / "Devices"** with the Lucide `Speaker` icon (the device itself; Zones keep `Volume2`).
- **h1 is "Geräte"**, not the device name: the page title stays stable while swiping, the name is already the editable h2 in the card and in the sticky bar, and a changing h1 would be announced on every swipe.
- Route `/local-control` is removed; `/presets` should redirect to `/devices`.

## New i18n keys (English text, German translation; Swedish in the prototype for the length test)
| Key | EN | DE |
| --- | --- | --- |
| `nav.devices` | Devices | Geräte |
| `devices.title` | Devices | Geräte |
| `device.presetsTitle` | Saved stations | Gespeicherte Sender |
| `device.findStation` | Find station | Sender suchen |
| `device.sourceChoose` | Choose source | Quelle wählen |
| `device.sourceCurrent` | Now: {{source}} | Aktuell: {{source}} |
| `device.sourceSwitching` | Switching to {{source}}… | Wechsle zu {{source}}… |
| `device.sourceSwitched` | Source changed: {{source}} | Quelle gewechselt: {{source}} |
| `device.sourceFailed` | Switching to {{source}} failed. The device is not responding. | Umschalten auf {{source}} fehlgeschlagen. Das Gerät antwortet nicht. |
| `device.sourceRetry` | Try again | Erneut versuchen |
| `device.sourceStandby` | Switch the device on to change the source. | Zum Umschalten das Gerät einschalten. |
| `device.sourceExternal` | {{source}} was started in the app and cannot be chosen here. | {{source}} wurde in der App gestartet und lässt sich hier nicht wählen. |
| `device.sourceRadio` | Radio starts from the presets or the station search. | Radio startet über die Presets oder die Sendersuche. |
| `device.standbyHint` | Device on standby. Switch it on to listen. | Gerät im Standby. Einschalten, um Musik zu hören. |
| `device.noControl` | Playback is controlled on the connected device. | Die Wiedergabe wird am angeschlossenen Gerät gesteuert. |
| `device.zoneMaster` / `device.zoneMember` | Zone: master / Zone: member | Zone: Master / Zone: Mitglied |
Existing keys reused: `player.prevTrack`, `nextTrack`, `play`, `pause`, `playbackTitle` (added in stage 9), `player.sourceTitle`, `player.source.*`, `presets.*`.

## What changes against stage 8
- Presets page and Local control page become one page and one card (`.dv-*`). `LocalControl.tsx` page, its route and nav entry go; the card component of Local control and `RadioPresets` merge into `DeviceCard`.
- Presets move from the page into the card; the "Preset Hinweise" box is dropped (the empty slot already says what to do; tell me if you want it back).
- Cover play overlay on the art is removed (the keys replace it).
- New: track keys, source row, standby state of the whole card, zone badge in the header.
- Unchanged: sticky device bar, swipe, bottom bar, offline banner and remove footer, header layout, preset slot size, volume slider.

## Open points
1. **Light theme is a draft.** The app has no light tokens. `theme-light.css` maps the existing tokens (text on card at least 7:1, secondary text at least 5.5:1). Components with hard-coded white (primary buttons, pressed chips, active preset text) are patched in that file; the offline banner, toasts and dialogs were not checked in light.
2. **Swedish and German texts are only checked for the new keys** (and a few existing ones). Other strings fall back to German in the prototype.
3. "Sender suchen" and the empty preset slot are not wired to the search dialog in this prototype (the dialog exists as page `search`).
4. Standby makes presets inert. If you prefer "tap a preset wakes the device", only the `dv-inert` wrapper on the presets changes.
5. Deezer, Pandora and Amazon use the same flag as Spotify; they are not separate prototype cases.
