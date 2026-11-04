# Design briefing — quick timer, device settings card, scheduled timers, stream recovery

Audience: Claude Design (and the integrating developer). Status: draft for the maintainers' review.

Related specs: #537 sleep timer, #543 scheduled actions, #583 scheduled sessions with end phase, #551 stream recovery, #557 device settings.
Binding rules: [UI quality checklist](../UI_QUALITY_CHECKLIST.md), rules 1–7. State in the delivery how each rule is met and where it deviates.

## 1. Starting point

Build on the existing handoff `design/oct-handoff` (`design/claude-design-handoff/`), stage 13 (`OCT App Stufe 13.dc.html`, `project/app13/`):

- Device card from stage 10 with the three source buttons (stage 12) and preset rows as toggles with their own "change" button (stage 13, variant V1, rows fixed at 76 px).
- Same tokens, `theme-light.css`, dark and light, widths 320 / 390 / 768 / 1280 px, German and Swedish texts including very long names.
- Stage 13 leaves header, zone badge, now playing, track keys, **volume**, remove footer, offline, standby, swiper and sticky bar unchanged. This briefing adds to them; it must not change them.

The handoff contains **no** design for the sleep timer, scheduled timers, device settings or stream recovery. All four below are new.

## 2. What exists today (behaviour is fixed, visuals are not)

| Feature | Behaviour (backend contract) | Current placeholder UI |
|---|---|---|
| Sleep timer (#537) | One timer per device. Duration 1–720 min, fade-out 0–300 s (default 30 s), end action `stop` or `standby`. Restores the original volume afterwards. Survives a server restart. Cancel at any time. The countdown follows the server clock. | A plain card under the volume slider on the Devices page (presets in minutes, "Custom…" in minutes). |
| Stream recovery (#551) | Opt-in per installation: restarts a stream that dropped (device reports an invalid source). Configurable window and attempts, plus an activity log (time, device, station, preset, outcome, play time, attempts). | A section on the global Settings page (checkbox, two number fields, refresh button, table). |
| Device settings (#557, backend only) | Per device: name, bass, language, clock, power saving. The frontend waits for the external PR #515. | None. |
| Scheduled timers (#543, #583, not built) | See section 4. | None. |

## 3. Quick timer on the device card

Goal: fast access to a one-off timer that is already set up in time.

Requirements:

- Lives **on the device card** (Devices page), next to the volume control. It must not move or resize the card in any state (rule 1): reserve the height, no element that appears suddenly.
- Entry by **hours and minutes** (two inputs or a stepper pair, total 1 min – 12 h, shows the total, e.g. "= 1 h 47 min"). Quick presets (e.g. 15 / 30 / 45 / 60 / 90 min) are allowed if they save taps.
- Remembers the last used duration, fade-out and end action per browser.
- Fade-out (off, 10, 30, 60, 120 s; default 30 s) and end action (stop / standby) are secondary: collapsed behind a single control, not shown by default.
- States to design: no timer · input invalid · starting · running (countdown, ends-at time) · fading out · ending · ended or replaced elsewhere · cancel · server error with retry · device offline · device in standby · zone member.
- The countdown is announced politely, but **not every second** (rule 4); a cancel control is always reachable by keyboard; the focus stays where it was after start, cancel and end.
- A running timer is also visible in the collapsed or compact state of the card (small label with remaining time), so the user sees that a timer is active without opening anything.

Open questions for Design: is one row with "Timer" opening an inline panel better than a permanent block? How does the timer coexist with the swiper and the sticky bar?

## 4. Device settings card (new) with scheduled timers

Goal: next to the Setup Wizard and the Restore Wizard, every device gets a **"Device settings"** card. It opens a settings view for that device.

Contents of the settings view:

1. **Device settings** (#557): name, clock (time), language, bass, power saving. Each shows its current value, a save action and a per-field error. Fields the device does not support are hidden or disabled with a reason.
2. **Scheduled timers** (#543, #583), a list with **multiple entries**:
   - Each entry: weekdays (multi-select, Mon–Sun, shortcuts "weekdays" and "weekend"), time of day (hour and minute), action, enabled switch.
   - Action `play preset` (slot 1–6), with optional start volume and fade-in; optional **end phase**: "switch off after" hours and minutes, fade-out (off / 10 / 30 / 60 s) and end action (stop / standby).
   - Action `stop` or `standby`, with optional fade-out.
   - Example the design must make easy: "Mon–Fri 07:00" and "Sat–Sun 09:00" as two entries; "Tue and Fri–Sun 14:44, preset 2, switch off after 47 min with fade-out".
   - Per entry: next run, last run result (success, skipped, failed with reason), run now, edit, delete (with confirmation).
   - Empty state, loading state, error state, offline device, many entries (list stays calm; adding and removing an entry must not make the page jump).
3. **Time zone** is shown next to the list (the schedule uses the server's time zone). The design must show it clearly, because a wrong zone makes every entry wrong.

Quick timer (section 3) is activated on the device card; scheduled timers are activated here. A running quick timer shows up in this view as read-only status with a link to the card.

Open questions for Design:

- Form pattern for an entry on phone widths: inline expanding row, bottom sheet or full page?
- Weekday selector that meets 44 px targets at 320 px (rule 5) and works without colour alone (rule 2).
- How to show an entry that is switched off, one that is overdue after a restart, and a device that is offline when it should have run.

## 5. Stream recovery on the Settings page

Keep it on the global Settings page, but give it the same look as the rest of stage 13: opt-in switch with explanation, window and attempts fields with inline validation, activity log as a table at ≥768 px and as a list of cards below (no horizontal scroll, rule 4/6), refresh with polite status text, empty, loading and error states. No behaviour change.

## 6. Deliverables

- Prototype pages like the existing stages, with state switches for: device (online, offline, standby, zone member), timer state, language (de, sv), theme (dark, light), width (320, 390, 768, 1280), long names.
- For every new component: the list of CSS tokens used, new components only where an existing one (`ui-base`, dialogs, toasts, sticky device switch) does not fit.
- Drop-in **React/CSS** like the earlier stages (props, hooks, API calls and `t()` keys unchanged where they exist), plus an i18n additions file in en / de / sv.
- The rule 1–7 table with evidence (layout audit at 320 / 390 / 768 / 1280, dark and light, contrast, 44 px targets, keyboard order and focus, screen reader names and live regions).
- Open points and deviations listed explicitly.

## 7. Product decisions needed before or during design

1. **Time zone of schedules:** server time zone (simple, matches the device clock) or per entry? #583 puts per-schedule time zones out of scope; the design should assume the server time zone.
2. **What a missed run does** (server was off at the start time): the backend rules of #543 apply; the design needs a visible "missed" state.
3. **Quick timer vs scheduled end phase:** one timer per device. A scheduled start with an end phase replaces a running quick timer. The UI must say so when the user starts one while the other is active.
4. **Where "Device settings" opens from:** card button, device menu, or the setup badge. The maintainers decide.

Hardware behaviour (pause vs stop, power, fades on the real device) is not verified yet; the design must not depend on it.
