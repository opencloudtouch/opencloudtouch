# Stage 8: remove a device, online and offline

Prototype: `OCT App Stufe 8.dc.html` (Presets and Local control, device online / offline / last device, 320 to 1280 px). Files: `DeviceRemove.css` (new, after `RadioPresets.css` and `LocalControl.css`; replaces `.rp-remove`), `i18n-stage8-additions.json` (DE/EN), frame in `stage8-frame.html` + `frame-pages.js`.

## Design
- **One place, one button, one label.** A footer row at the bottom of the device card (hairline above, 44 px button, full card width): `[trash] Gerät entfernen`. It sits at the same spot in Presets and Local control, online and offline. Not in the header: the header grid (power, name, setup badge) is full and a destructive button next to power invites mis-taps.
- **Emphasis follows the state, nothing else changes.** Online: quiet ghost button (danger text colour, no border, tint on hover). Offline: the existing `.btn-danger-outline`, directly below the offline banner (banner explains, button acts). The offline card also shows the `offline` setup badge and disabled presets, as before.
- **Same confirm dialog (`alertdialog`, small) in both states**, focus on "Abbrechen". It names the device (name + IP) and the text says what happens: online ("erreichbar … Presets werden gelöscht, das Gerät selbst bleibt unverändert, die nächste Suche kann es wieder hinzufügen"), offline (same, without the reachable remark). Confirm button is the solid `btn-danger`.
- **After removal:** toast "„Küche“ wurde entfernt." (6 s), the swiper moves to the neighbour (previous one if the last was removed), dots and count shrink; with no device left, an empty state with a link to Settings.

## Notes for the TSX
- Move the delete button out of `{deviceOffline && …}` into a footer `<div className="dm-foot">` at the end of `.rp-card` and `.lc-card`; classes: `btn dm-remove` + (`btn-danger-outline` if offline, else `btn-ghost dm-quiet`). Add the same `ConfirmDialog` + `deleteCurrentDevice` to `LocalControl` (it had none); message key by `deviceOffline`.
- Assumption: `deleteDeviceById` also removes the presets of that device. If not, change the dialog text.
- Risk for online devices: auto-discovery can add the device again at the next scan (the dialog says so). If you want removal to stick, the backend needs an "ignored" flag; not designed here.
- New keys: `presets.removeDevice`, `removeDeviceTitle`, `removeDeviceOnline`, `removeDeviceOffline`, `removeDeviceConfirm`, `deviceRemoved`, `noDevicesTitle`, `noDevicesHint`, `goToSettings` (the old `presets.deleteDevice`, `confirmRemoveDevice*` can go).
- Tests: the remove button now exists for online devices too (`data-test="device-remove"`); tests that expect it only when offline must change.
