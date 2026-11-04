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

## 1a. Consistency and design principles (binding, not a style hint)

The new screens must look and behave like the stages 5–13 that already exist. Before drawing anything, read and apply these files of the handoff (`design/claude-design-handoff/project/`):

| Source | What it fixes |
|---|---|
| `app/ui-base.css`, `app/tokens.css` | Tokens, type scale (`--fs-*`), buttons (`.btn-*`), `.ui-select`, `.ui-state`, `.wz-status`, spinner, focus ring, motion tokens. Reuse these; new tokens only with a written reason. |
| `app/STAGE5-NOTES.md` | Shell, dialogs (`Modal`, `ConfirmDialog`), toasts, empty state, skeletons, class prefixes, heading structure (one `h1`, `h2` per section), Lucide-style icons (no emoji). |
| `app7/STAGE7-NOTES.md` + `Settings.tsx/.css` | Section pattern (`h2` with `aria-hidden` icon, card), form pattern: real `<label>`, hint and error share **one reserved slot** (no jump), `role="alert"` errors, busy buttons keep their width, save shows a spinner plus a hidden `role="status"`. Used for stream recovery and device settings. |
| `app8/STAGE8-NOTES.md` | Destructive actions: one place, one label, same confirm dialog online and offline, focus on "Cancel", the text says what happens. Used for deleting a schedule entry. |
| `app10/STAGE10-NOTES.md`, `app13/STAGE13-NOTES.md` | Card order and the reasoning behind it (below), fixed heights, state shown by shape plus word (never colour alone), 76 px rows. |
| `wizard/wizard-base.css`, `app7`/`app10` offline banner | Wizard entry cards, status boxes, offline handling. The "Device settings" card must sit with the Setup and Restore entries like one of them. |
| `app13/REVIEW-FULL-UI.md`, `REVIEW-STAGE13-IMPLEMENTATION.md` | Open findings of the last review. Do not repeat them in new screens. |
| `docs/UI_QUALITY_CHECKLIST.md` | Rules 1–7. |

Principles that these files already follow, and that apply to every new screen:

1. **Order by use.** The card runs: what plays → how to control it → how loud → what else to play → rarely used → remove. The designer decides where each new element goes and explains the choice with this order, including how the card stays calm on 320 px where it is already about 1450 px tall.
2. **One place, one control, one label.** A function exists once. The quick timer is not repeated in settings; scheduled timers are not repeated on the card.
3. **Reserve space.** Every state line, hint, error and countdown has a reserved slot with a fixed height. Appearing, running and ended states change content, not size.
4. **State = shape + word + icon**, never colour alone; disabled, busy and failed are distinct from each other.
5. **Quiet by default, emphasis by state.** Secondary options (fade-out, end action) are collapsed; destructive actions are ghost until they matter.
6. **Same component for the same job.** Selects are `.ui-select`, toggles and chips are the existing ones, dialogs are `Modal`/`ConfirmDialog`, notices are toasts or `.wz-status`. A new component needs a sentence on why no existing one fits.
7. **Phone first, large screens use the space.** 320/390 one column; from 1024 px the two-column card of stage 10 (left: playing, keys, volume; right: presets, source). Placement within the layouts is the designer's decision.
8. **Texts through i18n keys**, written for the user, German and Swedish checked with long strings.

"Just drawing" is not accepted. The delivery must justify each placement and each new component against this list (one line each), name the existing pattern it reuses, and list every deviation with the reason. A screen without that justification is sent back.

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

- Lives **on the device card** (Devices page), at a position the designer chooses and justifies (section 1a). The only given is the location: the device card. It must not move or resize the card in any state (rule 1): reserve the height, no element that appears suddenly.
- Entry by **hours and minutes** (two inputs or a stepper pair, total 1 min – 12 h, shows the total, e.g. "= 1 h 47 min"). Quick presets (e.g. 15 / 30 / 45 / 60 / 90 min) are allowed if they save taps.
- Remembers the last used duration, fade-out and end action per browser.
- Fade-out (off, 10, 30, 60, 120 s; default 30 s) and end action (stop / standby) are secondary: collapsed behind a single control, not shown by default.
- States to design: no timer · input invalid · starting · running (countdown, ends-at time) · fading out · ending · ended or replaced elsewhere · cancel · server error with retry · device offline · device in standby · zone member.
- The countdown is announced politely, but **not every second** (rule 4); a cancel control is always reachable by keyboard; the focus stays where it was after start, cancel and end.
- The user must be able to see at a glance that a timer is active and how long it has left, without opening anything. How is a design decision.

Everything about form, position and interaction pattern is left to Design. Only constraint: it has to coexist with the existing swiper and sticky device bar.

## 4. Device settings card (new) with scheduled timers

Goal: every device gets a settings page of its own. It holds the device settings and the scheduled timers. The only given is the location (a per-device settings page); how it is reached, how it is structured and how it relates to the Setup and Restore wizards is up to Design.

Contents of the settings view:

1. **Device settings** (#557): name, clock (time), language, bass, power saving. Each shows its current value, a save action and a per-field error. Fields the device does not support are hidden or disabled with a reason.
2. **Scheduled timers** (#543, #583), a list with **multiple entries**:
   - Each entry: weekdays (multi-select, Mon–Sun), time of day (hour and minute), action, enabled switch.
   - Action `play preset` (slot 1–6), with optional start volume and fade-in; optional **end phase**: "switch off after" hours and minutes, fade-out (off / 10 / 30 / 60 s) and end action (stop / standby).
   - Action `stop` or `standby`, with optional fade-out.
   - Example the design must make easy: "Mon–Fri 07:00" and "Sat–Sun 09:00" as two entries; "Tue and Fri–Sun 14:44, preset 2, switch off after 47 min with fade-out".
   - Per entry: next run, last run result (success, skipped, failed with reason), run now, edit, delete (with confirmation).
   - Empty state, loading state, error state, offline device, many entries (list stays calm; adding and removing an entry must not make the page jump).
3. **Time zone:** the schedule uses the server's time zone. The design must make it clearly visible, because a wrong zone makes every entry wrong. Where is up to Design.

Quick timer (section 3) is activated on the device card; scheduled timers are activated on the device settings page. Whether and how the two reference each other is up to Design.

Open questions for Design:

- Form pattern for an entry on phone widths: inline expanding row, bottom sheet or full page?
- Weekday selector that meets 44 px targets at 320 px (rule 5) and works without colour alone (rule 2).
- How to show an entry that is switched off, one that is overdue after a restart, and a device that is offline when it should have run.

## 5. Stream recovery on the Settings page

It stays on the global Settings page (no move). Content, unchanged in behaviour: opt-in switch with explanation, window and attempts fields with inline validation, activity log (time, device, station, preset, outcome, play time, attempts), refresh, empty, loading and error states. Layout is up to Design; it must follow the existing look and the UI checklist (no horizontal scroll, rules 4 and 6).

## 6. Deliverables

- Prototype pages like the existing stages, with state switches for: device (online, offline, standby, zone member), timer state, language (de, sv), theme (dark, light), width (320, 390, 768, 1280), long names.
- For every new component: the list of CSS tokens used, new components only where an existing one (`ui-base`, dialogs, toasts, sticky device switch) does not fit.
- Drop-in **React/CSS** like the earlier stages (props, hooks, API calls and `t()` keys unchanged where they exist), plus an i18n additions file in en / de / sv.
- A **consistency table**: for every new screen and component the existing pattern or file it reuses (section 1a), or the reason for a new one.
- The rule 1–7 table with evidence (layout audit at 320 / 390 / 768 / 1280, dark and light, contrast, 44 px targets, keyboard order and focus, screen reader names and live regions).
- Open points and deviations listed explicitly.

## 7. Product decisions needed before or during design

1. **Time zone of schedules:** server time zone (simple, matches the device clock) or per entry? #583 puts per-schedule time zones out of scope; the design should assume the server time zone.
2. **What a missed run does** (server was off at the start time): the backend rules of #543 apply; the design needs a visible "missed" state.
3. **Quick timer vs scheduled end phase:** one timer per device. A scheduled start with an end phase replaces a running quick timer. The UI must say so when the user starts one while the other is active.

Hardware behaviour (pause vs stop, power, fades on the real device) is not verified yet; the design must not depend on it.
