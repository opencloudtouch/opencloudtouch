# UI quality checklist

Every UI design and every UI change is checked against these rules, whatever the layout looks like. They apply to **every view, state and size**, including settings, menus and dialogs. If an idea conflicts with a rule, the rule wins; deviations are stated and justified in the design delivery or the pull request.

> Related: [Definition of Done](DEFINITION_OF_DONE.md) · [Definition of Ready](DEFINITION_OF_READY.md) · [Architecture](ARCHITECTURE.md)

## How it is used

| When | Who | How |
|---|---|---|
| **Design brief** (spec issue or prompt to the designer) | Spec author | The brief names these rules as binding and asks the designer to state how the design meets rules 1–7 and where it deviates. |
| **Design delivery** | Integrating developer or agent | Tick each rule against the prototype before implementing. A rule that is not met is sent back to the designer with the concrete finding; it is not silently fixed in code. |
| **Implementation / pull request** | Author, then reviewer | Tick each rule against the running app (automated checks below plus the manual checks). Mark rules that cannot apply `n/a` with a reason. |

## The rules

| # | Rule | Requirement | Verified by |
|---|---|---|---|
| 1 | **Calm UI** | Switching a source, loading and switching devices never judder, jump or flash. No layout shift: reserved or fixed heights and placeholders instead of elements that appear suddenly. Transitions are short and smooth; with `prefers-reduced-motion` there is no movement. The "switching" and "failed" states do not move the card either. | Manual (iPhone/Safari and desktop, throttled CPU); layout audit for overlap and overflow (`tests/e2e/support/layoutAudit.ts`) |
| 2 | **Contrast** | Text at least 4.5:1, large text and controls at least 3:1, in light **and** dark mode, including disabled and active elements. A state (active source, playing preset, error) is never shown by colour alone: add shape, icon, fill or text. | axe (`tests/e2e/audit/accessibility-audit.cy.ts`); manual check of states axe cannot reach |
| 3 | **Keyboard** | Everything works without a mouse, in a logical order, with a clearly visible focus. After switching or closing a dialog the focus stays where the user was. No keyboard traps. Groups (sources, presets) document their arrow-key behaviour. | Cypress keyboard flows; manual tab-through |
| 4 | **Screen reader and low vision** | Sensible roles, names and states (active, pressed, disabled, busy). Changes are announced politely (`role="status"`), errors immediately (`role="alert"`). Icon-only controls have a name; decoration is hidden. Works at 200 % zoom and enlarged text without horizontal scrolling or clipped text (reflow from 320 px). | axe; unit tests on roles and names; manual VoiceOver/TalkBack pass for new patterns |
| 5 | **Operability** | Tap targets at least 44 px with enough space between them. Nothing is reachable only by hover or swipe; every swipe has an alternative. | Layout audit; manual |
| 6 | **All sizes** | 320, 390, 768 and 1280 px, light and dark. Large screens use the space sensibly instead of stretching the phone layout. | `tests/e2e/responsive.cy.ts` and the layout audit on all widths |
| 7 | **Consistency** | Existing tokens, components and patterns (`ui-base`, dialogs, toasts, sticky device switch). All text through i18n keys in all 10 locales; long German and Swedish texts fit. | Key-parity and orphan-key unit tests; layout audit with long texts |

## Review checklist (copy into the design review or the PR)

- [ ] 1 Calm UI: no judder or layout shift when switching, loading, failing; reduced motion respected
- [ ] 2 Contrast: text 4.5:1, controls 3:1, light and dark; no state by colour alone
- [ ] 3 Keyboard: full operation, order, visible focus, focus kept after changes, no traps
- [ ] 4 Screen reader / low vision: roles, names, states, live regions, 200 % zoom without clipping
- [ ] 5 Operability: 44 px targets, no hover- or swipe-only action
- [ ] 6 All sizes: 320, 390, 768, 1280 px, light and dark
- [ ] 7 Consistency: tokens and components reused, texts in 10 locales, long texts fit
- [ ] Deviations from a rule are listed with the reason and approved

## Scope notes

- Automated checks (axe, layout audit) are a floor, not proof. Rules 1, 3 and 4 need a manual pass for every new pattern.
- A finding against the design (not the code) goes back to the designer with the rule number and the concrete state, size or theme where it fails.
