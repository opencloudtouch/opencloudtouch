# Design review: implementation after stage 13

Reviewed: `01-devices-page`, `02-card-parts`, `03-device-card.css`, `04-swiper-bar.css`, `05-zones`, `06-about`, `07-app-shell.css` against `STAGE13-NOTES.md` and `theme-light.css`.
Contrast values are computed from the CSS tokens (WCAG 2.x relative luminance), not measured in a browser.

## Verdict on the 8 changes

| # | Change | Verdict |
| --- | --- | --- |
| 1 | Presets editable in standby / as zone member, only start locked | **Approved.** Better than inert rows. One condition, see A. |
| 2 | Zone slave: source and preset start disabled, hint shown | **Approved with changes**, see A. |
| 3 | "Presets" source plays last preset, else first, else warning toast | **Approved.** Toast fix in D1. |
| 4 | Failure alert floats over the cover | **Approved with one bug fix**, see B. |
| 5 | No layout jumping | **Approved.** All reserved sizes match the design rules (76 px rows and keys, 32 px now-playing row, 56 px update slot). |
| 6 | Sticky bar no longer overlaps the card, 8 px gap | **Approved.** |
| 7 | Toast lists new devices one per line | **Approved**, see E. |
| 8 | Nav entry "Devices / Geräte" | **Approved.** Use the same word for the page `<h1>` (already so) and the swedish key ("Enheter"). |

## A. Standby and zone member (open questions 1, 2)

Behaviour is acceptable. Presets should look different in one respect:

1. **The hint is invisible.** `#dv-slave-hint` is `visually-hidden`; sighted users only see the "Slave" badge and dimmed controls, with no reason. Show one visible line under the zone badge: "Wird von {master} gesteuert" (en: "Controlled by {master}"). One line, 20 px, reserved only when `isZoneMember`.
2. **Do not dim the state line.** `.pr--dis .pr-main { opacity: .6 }` puts "Läuft" / "Pausiert" at 2.94:1 (light) on a slave that follows its master. Disabled controls are exempt from WCAG, but this is status information. Instead of opacity: keep text at full strength, remove hover/press feedback, `cursor: default`, and drop the tinted number badge to the neutral fill. The change button stays fully active (it already is), which now reads correctly: the divider separates "locked" from "editable".
3. **Standby:** starting a preset wakes the device, while the source buttons are inert. That is consistent as long as the standby card keeps its hint "Gerät im Standby". No visual change.
4. Standby and slave source buttons at 0.6 opacity: fine (exempt, state is carried by `aria-disabled` and the hint).

## B. Source failure alert

- **Bug:** the alert lives inside the wrapper that gets `inert` in standby. If the device goes to standby while the alert is open, it cannot be closed or retried. Clear `switchFailed` when `isStandby` becomes true.
- Starting via the "Presets" button sets both `failedPreset` (row says "Start fehlgeschlagen") and `switchFailed` (alert). Two messages for one failure. Keep both, but name the station in the alert ("SWR3 konnte nicht gestartet werden") and make Retry restart that same preset.
- Alert is a scroll container (`overflow:auto`): give it `tabindex="0"` only if content can actually overflow at 320 px, otherwise `overflow: hidden`. Escape closes it and returns focus to the source button that failed.

## C. Neighbour sliver (open question 3): drop it

At the page padding it is an 8 px wide, 1 px bordered strip 4 px from the screen edge. It reads as a clipped rendering glitch, depends on `--space-md`, and in light the border (`#cfd5de` on `#f1f3f6`) is nearly invisible. The swipe is already announced by the arrows and dots directly above the card, and cue 1 (arrow highlight while dragging) stays. Remove `::before` / `::after` of `.ds-viewport` in the narrow media query and set `overflow-x: clip` there as on desktop (keeps focus rings, `padding: 2px`).

## D. Light theme contrast (open question 4)

Fine (all ≥ 4.5:1 text, ≥ 3:1 graphics): running row text 12.9, secondary on running row 5.7, secondary on pressed tint 5.0, primary frame on running row 4.4, source button idle border 3.8, device dots idle 3.4, active dot 7.3, danger text 6.5, power-on 4.8.

Needs a fix:

1. **Toast: text 1.34:1.** `.toast` hard-codes `#2f2f2f` but takes `--color-text-primary` (`#14171c` in light). Secondary text and close icon 1.7:1. Add `--toast-bg` and `--toast-text` tokens: dark `#2f2f2f` / `#f2f2f2`, light `#ffffff` / `--color-text-primary` with the coloured border and `--shadow-md`. Warning icon colour `#ffc107` only works on dark; in light use `#8a6100`.
2. **Dot hover: 1.11:1.** `.ds-dot:hover::before { background:#fff }` on the light bar `#f1f3f6`. Use `var(--color-text-primary)`; the light override currently changes `color`, which this rule does not use.
3. **Monthly supporters gold `#f5c542`: 1.62:1 on the white card.** Needs a light variant (dark amber, ≥ 4.5:1, e.g. `#8a5a00`, no white sheen) and `generateGradientColor` must take the theme (its "≥ 5.2:1" holds for the dark card only).
4. **Superseded, see `REVIEW-FULL-UI.md`:** `--color-accent` is `#0066cc` (5.6:1 with white), no light override needed. The missing light token is `--focus-ring` (#8ab8f0, 2.1:1 on white): set it to `#0f4f98`.
5. Station avatars (`#fff` on `getAvatarColor`): check that the generated colours are dark enough in both themes; I could not verify without the function.

## E. Smaller points

- **Supporters placeholder (open question 3b): yes, a skeleton.** Same silhouette as the loaded block: card outline, centred heading line, 4 lines of varying width (static, no shimmer under `prefers-reduced-motion`), total height stays 220 px. Because the list is cached, it only appears on the first visit. Keep `aria-hidden` and let `aria-busy` live on the section.
- Toast with many devices: cap at 4 lines and end with "+ N weitere". Longer text needs a longer display time, and Close must stay reachable by keyboard.
- Zone members (`.zn-member`) show the volume slider without a now-playing line per member; fine, no change.
- `.si-fail` top is fixed at 44 px; derive it from the header row (32 px + 12 px gap) with a variable so Swedish two-line headers cannot shift it.
