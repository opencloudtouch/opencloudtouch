# Stage 7: Settings, Diagnostics, About, Licenses

Folder `app7/` (nothing in `app/`, `app6*/` touched). Drop-in files: `Settings.tsx/.css`, `Diagnostics.tsx/.css`, `About.tsx/.css`, `Licenses.tsx/.css`, `Icon.tsx` (complete file, 7 new icons), `aboutUtils.ts` (complete file; only `generateGradientColor` changed, see 4). `App.tsx` unchanged.
Prototype: `OCT App Stufe 7.dc.html` (pages Einstellungen / Diagnose / Über / Lizenzen, widths 320 / 375 / 414 / 768 / 1280, four phone sizes, a state picker per page for every state in sections 3 to 6, 200 supporters with very long names, 10 devices with all three presence states, very long platform and firmware strings). The prototype frame is `app7/stage7-frame.html` + `frame-pages7.js` (markup mirrors the TSX 1:1; texts from `de-texts.json` + `i18n-stage7-additions.json`, German and English). The logo is a placeholder box in the prototype (the real `/images/logo/oct-logo-dark_539x539.png` is in the TSX).

## Verification (hit-test and audit, as agreed in 6d)
`Hit-Test + Audit` loads **29 states x 4 phone sizes (320x568, 375x667, 402x874, 430x932) = 116 states** in hidden frames. For every button, link, input, select and slider it scrolls the control to the middle of `<main>` and requires `elementFromPoint(centre of the first client rect)` to return the control or a descendant; it also runs the layout audit of the earlier stages (overflow, overlap, targets >= 44 px, contrast >= 4.5:1, focusable scroll regions) and checks that a scrolling `<main>` contains a focusable element.
**Result of the last full run: 116 states, 1072 controls, 1 finding** (below). Everything else: 0 covered controls, 0 audit findings.
- **Finding (not in my files): the error toast of the Diagnostics download covers the download button at 320x568.** The toast (8 s, `Toast.css`, fixed below the header, 2 to 3 lines on a phone) lands on the title row, exactly where the button that triggered it is. It has its own 44 px close button, so nothing is stuck, but for up to 8 s the button cannot be tapped again. Options (your decision, both are `Toast.css`, so "changes to earlier files"): (1) on `max-width: 768px` place toasts at the bottom (`bottom: calc(12px + env(safe-area-inset-bottom))`), (2) keep them at the top and shorten the error text. I did not change `Toast.css`.
- Two toasts also overlap the h1 in the audit (settings `toast=scan`, diag `toast=dgerr`): a toast is an overlay by design; not counted.
- Problems the check found in my own first version and that are fixed: (a) the supporters names faded in with `opacity`, which makes contrast checks that run during the animation fail (61 of 200 names also failed with the old colours, see 4); the animation is now scale only; (b) Diagnostics while the bundle is being created: the button was `disabled` and the scrolling `<main>` had no focusable element left (your `scrollable-region-focusable` case): now `aria-disabled` (D4).

## 1. Settings
- One column, `max-width: 800px`; h1, then two sections (`<section aria-labelledby>`, h2 with a Lucide icon `Search` / `FileText`, `aria-hidden`; no emoji).
- **Discovery card:** two method blocks (h3), separated by a hairline. **Scan button:** no more fixed `aria-label`; its name is its text and changes to "Suche läuft..." with `aria-busy="true"`; a visually hidden `role="status"` says `settings.deviceDiscovery.scanningStatus` while it runs (live region is always in the DOM). `min-width: 200px`, so idle and busy label have the same width. Primary action, full width at <= 480 px, first control of the page on a 568 px screen.
- **Manual IP:** a real `<label>` (`settings.manualIps.label`), the placeholder stays the example. Field, hint and error are wired: `aria-describedby` points to the hint, or to the error when there is one; `aria-invalid` on error; the error has `role="alert"`, an icon and sits **in the same reserved slot as the hint** (two lines high), so the page does not jump. Mono font in the field. Submit: spinner + `probing`, field and button disabled; `aria-busy` keeps the button at full opacity.
- **Log level:** label + the stage 5 `.ui-select`, appearance reset with an inline SVG chevron in a wrapper (visible in forced-colors, border from `.ui-select`); while the PUT runs the chevron becomes a spinner, the select is disabled, `aria-busy`, and a hidden status says `settings.logging.levelSaving`.
- **Download logs:** description, button with `Download` icon, **busy state** (spinner + `settings.logging.downloading`) and an **inline error slot** (`.wz-status--error`, `role="alert"`, `settings.logging.downloadFailed` with the error text), see S2.
- **Loading / error:** `.ui-state` card (spinner / alert icon), hidden h1 stays, error keeps h2, message and the Retry button (a focusable element).
- The page has focusable controls in every non-loading state; loading and error are short and do not scroll.

## 2. Diagnostics
- Header row: h1 and the **download button** (first focusable element of the page, no scrolling on a long device list). Busy: spinner + `bugReport.downloading`, `aria-disabled`, same width (`min-width: 19rem`, full width on phones).
- **Server / Database:** `<dl>` rows in a card (term above value below 480 px, two columns from 480 px, no horizontal scroll); version, Python, platform, level are mono and wrap (`overflow-wrap: anywhere`). I chose `<dl>` instead of `<table>`: a table that reflows needs `display` changes that drop the table semantics in Safari, and these are plain key/value pairs.
- **Discovery** shows an icon badge (check + "Aktiviert" / minus + "Deaktiviert"), not a coloured dot.
- **Devices:** one `article` per device (grid, one column on phones, `auto-fill 320px` above), h3 name + model, **presence badge** with icon and text (`Online` / `Länger nicht gesehen` / `Offline`; same 5 / 30 minute rule, same colours as before), then a `<dl>`: IP (mono), firmware (mono, long build strings wrap), setup status through the existing `StatusBadge` look (label shown, small), last seen (`toLocaleString()` or a dash with a hidden "unbekannt"), **SSH** as badge with icon and text (`Dauerhaft aktiv` / `Nicht aktiv`).
- States: loading and error in `.ui-state` (`role="status"` / `role="alert"`), no devices as a card with `Speaker` icon.
- `data-test` attributes unchanged: `diagnostics-page`, `-server`, `-db`, `-devices`, `-download`.

## 3. About
- Header: logo `<img alt="">` (the name follows), h1 "OpenCloudTouch", version badge (`ui-badge--info`, `v{{version}}`), skeleton while loading, nothing on failure; the slot is 32 px high in all three cases.
- **Build time line:** I recommend to **remove it** until `/health` sends `uptime` (#521): a line that has never been shown is dead UI. The markup stays (conditional, `ui-small`) so nothing breaks; deleting 3 lines of TSX is your call (A3).
- **Update check:** one slot (`aria-live="polite"`, min-height 56 px) with `.wz-status` boxes: checking (spinner), update available (`Sparkles`, text, "Release ansehen" button with external-link icon and hidden "(öffnet in neuem Tab)"), up to date (success, `CircleCheck`), dev build (`Wrench`). The available state is taller (button): one jump of about 40 px only when an update exists.
- **Supporters:** `<section>` with h2, `<ul>` of names in a card, centred, wrapping (`overflow-wrap: anywhere`, long handles and 90 character names wrap inside the card), font size by amount as before.
- **Links:** `<nav aria-label="Weitere Informationen">` list: GitHub (Lucide `Github`), Fehler melden (`Bug`), Diagnose (`Wrench`), **Lizenzen (new, A4)** (`FileText`), Unterstützen (`Coffee`). 56 px rows. External links end with an external-link icon + hidden "(öffnet in neuem Tab)"; internal ones with a chevron; the icons are `aria-hidden`, the old `›` characters are gone.

### Supporters: your four questions
(a) **Contrast.** The old function (lightness 55 / 65 %, saturation 60 to 80 %) reaches **2.0:1** on the card surface (#242424); **61 of 200 names fail 4.5:1**. The new one: **lightness 74 % / 80 %, saturation 55 to 75 %**, same hue sweep and same function signature. I computed the contrast over all hues in 0.5 degree steps for every combination: **minimum 5.2:1** (blue hues are the worst case); for comparison 72 / 78 % would give 4.71:1, 70 / 76 % 4.26:1. Monthly supporters are white (15.5:1) with a bold weight and a 2 px bottom line (not colour alone). `aboutUtils.ts` is delivered with this change (A5).
(b) **Tooltip.** `title` is invisible for keyboard, screen readers and touch. Remove it; the names are a normal list. As an alternative, a **single thank-you sentence** under the heading, chosen once per visit with the existing `getRandomThankYou(false, lang)` (A2). Remove the `<p className="ab-thanks">` line if you do not want it. Monthly supporters are announced through a hidden "(monatlicher Unterstützer)".
(c) **100+ names:** flex wrap with gaps; verified with 200 names, long names and handles at 320 px, no horizontal scroll.
(d) **Reduced motion:** the stagger is CSS only (`animation-delay: calc(var(--i) * 10ms)`, index capped at 40, so at most 0.4 s), scale only (no opacity, see Verification), switched off under `prefers-reduced-motion`.

## 4. Licenses
- h1 + description; three groups, each an `h2` and a card with a **list** (not a table): per library a link with the name (accessible name "{{name}} Website (öffnet in neuem Tab)", which starts with the visible text), version (`Version` + mono value) and licence badge. Phones: name and badge on the first line, version below; from 600 px one line in three columns. There is no icon-only link any more.
- Footer: compliance card (h2 with the h3 look; the heading order stays h1 > h2), project licence line (label from a key, link to `.../blob/main/LICENSE`, "Apache License 2.0", hidden new-tab text), **trademark notice** as a `.wz-status--warning` box with the `Alert` icon and `<Trans>` array form (`<strong>`, link to `TRADEMARK.md`), attribution block.
- The URLs now use the repository `opencloudtouch/opencloudtouch` that `About` already uses (the placeholder `yourusername` is gone). Dependency data is unchanged (outdated, your data fix).
- Focus: every row has a link, so `<main>` always has focusable elements.

## (a) New i18n keys (German and English, also in `app7/i18n-stage7-additions.json`)

| Key | DE | EN |
| --- | --- | --- |
| `settings.deviceDiscovery.scanningStatus` | Netzwerksuche läuft | Network scan running |
| `settings.manualIps.label` | IP-Adresse des Geräts | Device IP address |
| `settings.manualIps.hint` | Format: 192.168.1.10 | Format: 192.168.1.10 |
| `settings.logging.levelSaving` | Log-Level wird gespeichert | Saving log level |
| `settings.logging.downloading` | Wird erstellt... | Preparing... |
| `settings.logging.downloadFailed` | Logs konnten nicht heruntergeladen werden: {{error}} | Logs could not be downloaded: {{error}} |
| `diagnostics.ip` | IP-Adresse | IP address |
| `diagnostics.ssh` | SSH | SSH |
| `diagnostics.sshOn` / `sshOff` | Dauerhaft aktiv / Nicht aktiv | Permanently enabled / Not enabled |
| `diagnostics.statusOnline` / `statusStale` / `statusOffline` | Online / Länger nicht gesehen / Offline | Online / Not seen recently / Offline |
| `diagnostics.unknownValue` | unbekannt | unknown |
| `about.github` | GitHub | GitHub |
| `about.externalLink` | (öffnet in neuem Tab) | (opens in new tab) |
| `about.licenses` | Open-Source-Lizenzen | Open-source licenses |
| `about.linksLabel` | Weitere Informationen | More information |
| `about.supportersTitle` | Supp&lt;0/&gt;rters (heart icon in the slot) | Supp&lt;0/&gt;rters |
| `about.supportersLabel` | Unterstützer | Supporters |
| `about.monthlySupporter` | (monatlicher Unterstützer) | (monthly supporter) |
| `about.libraryWebsite` | {{name}} Website | {{name}} website |
| `about.licensesVersion` | Version | Version |
| `about.licensesGroup.frontend` / `backend` / `build` | Frontend / Backend / Build-Werkzeuge | Frontend / Backend / Build tools |
| `about.licenseProject` | OpenCloudTouch-Lizenz | OpenCloudTouch licence |
| `about.licenseApache` | Apache License 2.0 | Apache License 2.0 |
| `about.trademarkTitle` | Markenhinweis | Trademark notice |
| `about.trademarkText1` | OpenCloudTouch steht in &lt;0&gt;keiner Verbindung zur Bose Corporation&lt;/0&gt;. Bose® und SoundTouch® sind eingetragene Marken der Bose Corporation. | OpenCloudTouch is &lt;0&gt;not affiliated with Bose Corporation&lt;/0&gt;. Bose® and SoundTouch® are registered trademarks of Bose Corporation. |
| `about.trademarkText2` | Diese Software nutzt die öffentlich dokumentierten lokalen Schnittstellen von Bose-SoundTouch®-Geräten. Details stehen in der &lt;0&gt;TRADEMARK.md&lt;/0&gt;. | This software interfaces with Bose SoundTouch® devices using their publicly documented local APIs. See &lt;0&gt;TRADEMARK.md&lt;/0&gt; for details. |

`about.github` was removed in your clean-up and is re-added. Existing keys now used differently: `about.sectionTitle` (h2 in the footer), `common.enabled` / `common.disabled` (badge text). The old `about.licensesGroup` has no previous key. Other languages: the new keys fall back to English like the others.

## (b) Logic deviations and proposals
Deviations I made in the files (all small, tell me which you reject):
- **S1** `noValidate` on the IP form. With the `pattern` attribute and no `noValidate` the browser shows its own bubble and `handleAddIP` never runs for a wrongly formatted address, so `invalidFormat` is never shown in a real browser (jsdom does not enforce `pattern`). The code validation stays.
- **S2** Log download: `downloadState` ("idle" / "busy" / "error") and `downloadError`; the fetch/blob code is the same, moved into `handleDownloadLogs`; the `catch` still logs to the console and now also sets the inline error.
- **S3** Settings: `framer-motion` removed (the section fade-in is decorative; `motion.section` is a plain `section`).
- **D2** `Diagnostics`: `toSetupStatus()` guard and `StatusBadge` import, so the raw `setup_status` string (e.g. "complete" in your test data, which is not in the `SetupStatus` enum) shows as "Unbekannt" instead of crashing `StatusBadge`. No change to `StatusBadge` itself.
- **D3** Diagnostics: the download section moved above the sections in the DOM (tab order: download first). The `data-test` stays.
- **D4** Diagnostics: `aria-disabled` plus `if (downloading) return;` instead of `disabled`, so the button keeps focus and `<main>` keeps a focusable element (1.3 of your list).
- **A1** About: `framer-motion` removed (CSS stagger, see above). Names are `<li>` in a `<ul>`.
- **A2** One thank-you sentence instead of per-name `title` (`getRandomThankYou(false, lang)` is called once with `useMemo`). `getRandomThankYou` stays.
- **A3** Build time: see 3, recommend deleting.
- **A4** Link to `/licenses` in the list (new key `about.licenses`).
- **A5** `aboutUtils.ts`: new lightness / saturation in `generateGradientColor`.
- **L1** Licenses: footer headings h2 (h3 look), URL fix, `Trans` array form for the trademark text.
- Proposals not implemented: **D1** a Retry button in the Diagnostics error state (needs the effect to be callable again); **T1** toast position on phones (see Verification).

## (c) Tests to adapt
- **Settings:** the scan button used to have the constant name "scanButton" while scanning; its name is now the visible label ("Suche läuft..." while scanning). Tests that look it up while scanning by the idle name break. The IP input now has a label (`getByLabelText`); the error box has `role="alert"` (`getByRole("alert")`); the placeholder test is unchanged; "+ Add" is unchanged.
- **Diagnostics:** status dot `aria-label="green"` and the emoji `✅`/`❌` are gone (use the badge texts: Online, Permanently enabled, ...); setup status shows the `statusBadge.*` label ("Unknown" for "complete"), not the raw string; during the download the button is `aria-disabled="true"`, not `disabled` (`toHaveAttribute("aria-disabled", "true")`); server and device values are in `<dd>`, not `<td>`: `getByText` is unchanged, `getByRole("row")` / `cell` is not; the download button is the first button.
- **About:** `.supporter-name-wimmelbild` is `.ab-name` (list items); the `title` tooltip tests are gone; the heading is "Supporters" (accessible name), links have the extra hidden "(opens in new tab)" (`getByRole("link", { name: /GitHub/ })` still works, exact names do not); the emoji link labels (`🐛 ...›`) are gone; the framer-motion mock is harmless but no longer needed.
- **Licenses:** headers "Bibliothek / Version / Lizenz / Link" and the table are gone (list); `getByText(/About/i)` still finds exactly one element (the attribution h2); `getByText("React", { exact: true })` still works.
- **a11y / browser tests:** axe should find no new violations (names on every link and control, headings in order); `app-states.cy.ts` can add the states above.

## (d) Open points
1. Toast on phones covers the Diagnostics download button for up to 8 s (see Verification, T1).
2. `Toast` and the pages: toasts overlap the title row on phones in general; no change here.
3. The prototype uses a placeholder for the logo and a fixed thank-you sentence (`thankYouPhrases` is not in the prototype).
4. Build-time line (A3) and the Retry button (D1) are your decisions.
5. The Licenses data (versions, `latest`) is outdated; the page now shows exactly what the file contains.
6. `lic-name` links are underlined (links must not rely on colour); if you prefer them plain, add a visible hover state instead.
7. `Settings` keeps the stage 5 `.ui-select` look in forced-colors through the border and the inline SVG chevron; I could not test a real forced-colors session in the prototype.

## (e) Old CSS that can go
`Settings.css`, `Diagnostics.css`, `About.css`, `Licenses.css` are replaced by the new files of the same names. These global rules should no longer be used by any page after this stage (please `grep` before deleting): `.page`, `.page-title`, `.section-title`, `.section-icon`, `.section-description`, `.warning-box`, `.status-badge`, `.button-icon`, `.device-badge`, `.info-box`, `.loading-container`, `.loading-message`, `.error-container`, `.error-icon`, `.error-title`, `.error-message`, `.spinner-inline`, `.alert`, `.alert-error`, `.settings-card`, `.diagnostics-*`, `.status-dot*`, `.about-*`, `.supporters-wimmelbild*`, `.license-*`, `.lib-*`.

## (f) Changes to earlier files
None required. `Toast.css` is the one candidate (T1, your decision).
