# Design review: whole UI as implemented

Reviewed: `00-README` and files 01 to 11 (shell, Devices, device card parts, swiper, Zones, About, Licenses, Diagnostics, Firmware, 404, Settings, wizard base, setup wizard, restore wizard) against the stage 1 to 13 deliveries and `theme-light.css`.
Contrast figures are computed from the CSS tokens (WCAG 2.x), not measured in a browser. Scope of the wizard: I checked structure, tokens, hard-coded colours, focus and state handling; I did not diff every step's markup against the stage 1 to 4 deliveries (the files state "logic unchanged, markup restyled").
This replaces the shorter `REVIEW-STAGE13-IMPLEMENTATION.md` where they differ (see "Correction" at the end).

## 1. The 8 changes without Design

| # | Change | Verdict |
| --- | --- | --- |
| 1 | Presets editable in standby / as zone member | **Approved.** |
| 2 | Zone slave: source and start disabled, hint shown | **Approved with changes** (A). |
| 3 | "Presets" source plays last, else first preset, else warning toast | **Approved.** |
| 4 | Failure alert floats over the cover | **Approved with a bug fix** (B). |
| 5 | No layout jumping | **Approved.** Matches our fixed-height rules. |
| 6 | Sticky bar no longer overlaps the card | **Approved.** |
| 7 | Toast lists new devices per line | **Approved**, cap at 4 lines (E). |
| 8 | Nav "Devices / Geräte" | **Approved.** |

### A. Standby and zone member
- Behaviour is fine. The row should look different in one way only: do not dim the state text. `.pr--dis .pr-main { opacity: .6 }` puts "Läuft"/"Pausiert" at 2.9:1 in light. Keep text at full strength, remove hover/press, `cursor: default`.
- `#dv-slave-hint` is `visually-hidden`. The README says "the zone hint is shown", but sighted users only get the badge. Show one visible line under the zone badge ("Wird von {master} gesteuert"), 20 px, only for slaves.
- Standby: source buttons sit inside the `inert` wrapper, so they cannot be focused at all. That is fine; the "Standby" text and hint carry the reason.

### B. Failure alert
- **Bug:** the alert is rendered inside the wrapper that gets `inert` in standby. A device that goes to standby while the alert is open leaves an alert that cannot be closed. Clear `switchFailed` when `isStandby` turns true.
- "Presets" failing sets both `failedPreset` (row) and `switchFailed` (alert). Keep both, name the station in the alert and make Retry restart that preset.

### C. Neighbour sliver: drop it
8 px wide, 4 px from the screen edge, looks like a clipped render glitch, depends on `--space-md`, border nearly invisible in light. Arrows, dots and the drag cue already say "swipe". Remove the two pseudo-elements and restore `overflow-x: clip` on the viewport.

### D. Supporters placeholder: use a skeleton
Same silhouette as the loaded block (card outline, centred heading line, 4 lines of varying width), 220 px total, `aria-hidden`, static under reduced motion. Because the list is cached it shows on the first visit only.

## 2. Light theme (open question 4)

The app has `data-theme="light"` tokens only. Everything below comes from values that the light file does not override.

Passes: running/paused preset rows (text 12.9 and 15.5, state text 5.7), pressed tint (secondary 5.0), source buttons idle border 3.8, device dots idle 3.4 / active 7.3, danger text 6.5, success text 4.8 on tint, info badge 6.8, primary key and `.btn-primary` (white on `--color-accent` #0066cc = 5.6; the dark value already works, no light override needed).

Fails or needs a light value:
1. **`--focus-ring` (#8ab8f0) is not overridden: 2.06:1 on white, 1.85 on the page.** Every `:focus-visible` outline in the app (buttons, inputs, toggle, nav) misses the 3:1 for focus indicators. Set `--focus-ring: #0f4f98` in light (7+:1).
2. **Warning colour `#ffc107` as text or icon: 1.55:1** (`.ui-badge--warning`, `.wz-status--warning` icon, toast warning icon, Firmware "update available", Licenses trademark box). Light value `--warning-color: #8a5a00` (5.6:1 on the tint); the status box needs `--c` mapped the same way.
3. **Toast:** `#2f2f2f` background with `--color-text-primary` text: 1.3:1. Add `--toast-bg` / `--toast-text` tokens (dark: `#2f2f2f` / `#f2f2f2`; light: card white / primary text) and `--shadow-md`.
4. **Hard-coded `#fff` hovers:** `.ds-dot:hover::before` (1.1:1 on the bar), `.lic-name:hover` and `.lic-link:hover` (white on white card, text disappears on hover). Use `var(--color-text-primary)` or a darker accent step.
5. **Wizard progress circles:** "completed" is `var(--color-bg-darker)` on `#4caf50`: 2.3:1 in light (7.0 in dark). "Error" on `#f44336`: 3.0. Use fixed `#0d0d0d` text on the green and `#fff` on a darker red (`#c62828`, 5.6) so both themes pass; same for `.verify-phase--done .verify-phase-num`.
6. **Green borders `#4caf50`** (selected USB checklist, risk card, config "to" block, reboot done, skipped step): 2.8:1 on white, below the 3:1 of a component border. Use `--color-success` in light (#1f7a2b).
7. **Skeletons:** `.ui-skeleton` is a fixed dark gradient (#2c2c2c); on the light page it reads as black bars. Tokenise (`--skeleton-a/-b`).
8. **Monthly supporter gold `#f5c542`: 1.6:1** on white; needs a dark amber and no white sheen in light. `generateGradientColor` also has to take the theme (its 5.2:1 claim is for the dark card).
9. **Hover tints `rgba(255,255,255,.04..08)`** (`.ui-alert-close`, `.toast-close`, `.ui-badge` neutral fill, wizard SSH summary): invisible on light; use `rgba(var(--ink-rgb), .06)`.
10. Not verifiable here: station avatar colours (`getAvatarColor`, white text on generated colour). Please check both themes.

## 3. Other findings in the whole code

**Shell and shared**
- Nav, skip link, loading and error states, `Modal` on native `<dialog>`, focus return and scroll lock: all as designed. Nested `ConfirmDialog` inside the search modal works because of the top layer; keep it.
- At <= 360 px only the active nav label is visible. Acceptable (icons plus accessible names), but "Zones" and "Devices" use two audio icons of similar look; give Zones the `Link` or `Speaker` icon.
- `ConfirmDialog` has its own document `keydown` for Escape while `Modal` already handles it (`closeOnEscape={false}`). Fine; just keep one path when you touch it.

**Firmware page: not reachable and not real**
- No nav entry and no link from About: the page exists only by URL.
- Status is mock logic (`parseInt(version) >= 12`, with a comment that says ".6"). It shows a yellow "update available" warning for real devices. Show it only when the backend provides a version comparison; until then hide the status column and the warning, or label it "Preview".
- The disabled upload card and the "Warning" box are filler while nothing works. Remove both until the feature exists (we would rather ship an empty-state sentence than a disabled form).

**Settings**
- Log level `CRITICAL` is labelled "Off": say "Nur kritische Fehler" (it is not off), or keep the label and add a hint line.
- `.st-ip-msg { min-height: 39px }` reserves two lines of 13 px; fine. Success text for scan results is a toast only; a persistent line under the button ("3 neue Geräte gefunden") would help people who miss the 5 s toast.

**Diagnostics / Licenses / About**
- `aria-disabled` instead of `disabled` on the download button, back link on both pages, `dl` rows: good.
- The Licenses data is static ("latest"). Fine, but "latest" in a version column reads as unknown; show "n/a".

**Wizard**
- Shared tokens, `wz-status` family, 44 px targets, progress tracker with icon + number + label (not colour alone): consistent with stages 1 to 4.
- `global-demo-banner` with an emoji (DEV only): fine, never shipped.
- `.wizard-step-title:focus { outline: none }` is acceptable for the programmatic focus target only.
- Duplicate idioms (`.error-icon`, `.warning-icon`, `.failed-icon` next to `.wz-status`) remain in steps 3 to 8; merge them into `wz-icon` when you next touch those steps.

## 4. Smaller points on the earlier list
- Toast with many devices: cap at 4 lines plus "+ N weitere", and extend the display time with the line count (5 s is short for 4 lines).
- `.si-fail { top: 44px }`: derive from a variable so a two-line Swedish header cannot shift it.

## Correction to `REVIEW-STAGE13-IMPLEMENTATION.md`
Point D4 there said `--color-accent` might be a light blue. It is `#0066cc` (white on it 5.6:1), so no light override is needed. The real missing token is `--focus-ring` (item 1 above).
