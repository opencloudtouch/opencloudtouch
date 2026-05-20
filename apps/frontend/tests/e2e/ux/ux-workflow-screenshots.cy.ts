/**
 * UX Workflow Screenshots — Vollständige Visuelle Dokumentation
 *
 * Nimmt Screenshots aller UI-Elemente in folgenden Zuständen auf:
 *
 *   DARK  → Natives App-Theme (Bose dark background)
 *   LIGHT → Heller Analyse-Modus (weiß, für Design-Inspektion)
 *   STATE → Interaktions-Zustand (loading, error, focus, hover)
 *
 * Organisation der Screenshot-Dateinamen:
 *   {index}_{seite}_{beschreibung}__{dark|light}
 *   Beispiel: 02a_presets_full-page__dark.png
 *
 * Alle API-Calls werden intercepted — kein Backend erforderlich.
 *
 * Aufruf:
 *   npm run screenshots           → headless automatischer Lauf
 *   npm run screenshots:headed    → headed (für Hover-States)
 *   npm run screenshots:open      → Cypress Interactive UI
 *
 * Output: tests/e2e/screenshots/ux/
 */

// =============================================================================
// MOCK DATA (deterministische Fixtures für Screensh oots)
// =============================================================================

const DEVICE_ID_1 = "A1B2C3D4E5F6";
const DEVICE_ID_2 = "B2C3D4E5F6A1";
const NOW = new Date().toISOString();

const MOCK_DEVICES = [
  {
    device_id: DEVICE_ID_1,
    ip: "192.168.1.100",
    name: "Bose SoundTouch 30",
    model: "SoundTouch 30",
    firmware_version: "29.0.3.46291.53",
    mac_address: "A1:B2:C3:D4:E5:F6",
    last_seen: NOW,
  },
  {
    device_id: DEVICE_ID_2,
    ip: "192.168.1.101",
    name: "Bose SoundTouch 10",
    model: "SoundTouch 10",
    firmware_version: "28.1.3.46291.53",
    mac_address: "B2:C3:D4:E5:F6:A1",
    last_seen: NOW,
  },
];

// Gemischte Presets: einige belegt, einige leer
const MOCK_PRESETS_MIXED = [
  {
    id: 1,
    device_id: DEVICE_ID_1,
    preset_number: 1,
    station_uuid: "uuid-br3",
    station_name: "Bayern 3",
    station_url: "http://br-live.akacast.akamaistream.net/br3_live.mp3",
    source: "LOCAL_INTERNET_RADIO",
    station_homepage: "https://www.br.de/radio/bayern3",
    station_favicon: null,
    created_at: NOW,
    updated_at: NOW,
  },
  {
    id: 2,
    device_id: DEVICE_ID_1,
    preset_number: 2,
    station_uuid: "uuid-wdr2",
    station_name: "WDR 2",
    station_url: "http://wdr-wdr2-rheinland.icecastssl.wdr.de/wdr/wdr2/rheinland/mp3/128/stream.mp3",
    source: "LOCAL_INTERNET_RADIO",
    station_homepage: null,
    station_favicon: null,
    created_at: NOW,
    updated_at: NOW,
  },
  {
    id: 3,
    device_id: DEVICE_ID_1,
    preset_number: 3,
    station_uuid: "uuid-tunein",
    station_name: "Rock Antenne",
    station_url: "http://stream.rockantenne.de/rockantenne/stream/icy",
    source: "TUNEIN", // Cloud-abhängig → zeigt Cloud-Badge
    station_homepage: null,
    station_favicon: null,
    created_at: NOW,
    updated_at: NOW,
  },
  // Preset 4—6: leer (zeigt leere Platzhalter-Buttons)
];

// Alle Presets leer
const MOCK_PRESETS_EMPTY: never[] = [];

// Manuell hinzugefügte IPs
const MOCK_MANUAL_IPS = ["192.168.1.100", "192.168.1.101"];

// =============================================================================
// SCREENSHOT HELPERS
// =============================================================================

const SCR_OPTS = { overwrite: true, disableTimersAndAnimations: true, capture: "fullPage" } as const;
// Viewport-only capture: for fixed-position overlays (modals) and wide viewports
// where fullPage layout injection breaks flexbox centering.
const SCR_VIEWPORT_OPTS = { overwrite: true, disableTimersAndAnimations: true, capture: "viewport" } as const;

/**
 * Injiziert helles CSS-Override (Analyse-Modus, ohne dunklen Hintergrund)
 */
function injectLightMode(): void {
  cy.document().then((doc) => {
    if (doc.getElementById("ux-light-override")) return;
    const style = doc.createElement("style");
    style.id = "ux-light-override";
    style.textContent = `
      :root {
        --color-bg-dark:    #f8f9fa !important;
        --color-bg-card:    #ffffff !important;
        --color-bg-input:   #ffffff !important;
        --color-bg-hover:   #e9ecef !important;
        --color-text-primary:   #212529 !important;
        --color-text-secondary: #6c757d !important;
        --color-border:     #dee2e6 !important;
        --color-accent:     #0055aa !important;
      }
      body,
      html,
      .app,
      .app-main,
      #root {
        background: #f8f9fa !important;
        color: #212529 !important;
      }
      .app-header,
      .nav,
      .nav-container {
        background: #e9ecef !important;
        border-bottom: 1px solid #dee2e6 !important;
      }
      .nav-link { color: #495057 !important; }
      .nav-link.active, .nav-link[aria-current] { color: #0055aa !important; }
      .device-swiper,
      .device-card,
      .device-selector {
        background: #ffffff !important;
        border: 1px solid #dee2e6 !important;
        color: #212529 !important;
      }
      .preset-button {
        background: #ffffff !important;
        color: #212529 !important;
        border: 1px solid #dee2e6 !important;
      }
      .preset-button.assigned {
        background: #e8f0fe !important;
        color: #1a56db !important;
      }
      .preset-button.empty {
        background: #f8f9fa !important;
        color: #adb5bd !important;
        border: 1px dashed #ced4da !important;
      }
      .settings-card,
      .card,
      .section-card,
      .modal,
      .modal-content {
        background: #ffffff !important;
        color: #212529 !important;
        border: 1px solid #dee2e6 !important;
      }
      .empty-state,
      .wizard-container,
      .wizard-card {
        background: #ffffff !important;
        color: #212529 !important;
      }
      input, textarea, select {
        background: #ffffff !important;
        color: #212529 !important;
        border: 1px solid #ced4da !important;
      }
      .btn, button {
        color: #212529 !important;
        border-color: #ced4da !important;
      }
      .btn-primary, .btn[class*="primary"] {
        background: #0055aa !important;
        color: #ffffff !important;
      }
    `;
    doc.head.appendChild(style);
  });
}

/**
 * Entfernt den hellen CSS-Override
 */
function removeLightMode(): void {
  cy.document().then((doc) => {
    doc.getElementById("ux-light-override")?.remove();
  });
}

/**
 * Dark + light viewport-only screenshot (no fullPage layout injection).
 * Use for: position:fixed overlays (modals), wide viewports where height:auto breaks layout.
 */
function screenshotViewport(name: string): void {
  cy.wait(500);
  cy.screenshot(`${name}__dark`, SCR_VIEWPORT_OPTS);
  injectLightMode();
  cy.screenshot(`${name}__light`, SCR_VIEWPORT_OPTS);
  removeLightMode();
}

/** Single screenshot (dark only) with fullPage layout override */
function scrFull(name: string): void {
  cy.document().then((doc) => {
    if (!doc.getElementById("ux-fullpage-layout")) {
      const s = doc.createElement("style");
      s.id = "ux-fullpage-layout";
      s.textContent = [
        ".app { height: auto !important; min-height: 100vh !important; }",
        ".app-main { height: auto !important; overflow: visible !important; overflow-x: hidden !important; }",
        "html, body, #root { height: auto !important; }",
        ".wizard-step { opacity: 1 !important; transform: none !important; }",
        ".wizard-content-v2 > * { opacity: 1 !important; }",
        ".wizard-content-v2 > * > * > * { opacity: 1 !important; transform: none !important; }",
      ].join(" ");
      doc.head.appendChild(s);
    }
    void doc.body.offsetHeight;
  });
  cy.document().then(() => {});
  cy.wait(500);
  cy.screenshot(name, SCR_OPTS);
  cy.document().then((doc) => { doc.getElementById("ux-fullpage-layout")?.remove(); });
}

/**
 * Nimmt Screenshot in Dark + Light Modus auf
 */
function screenshotBoth(name: string, opts: Partial<Cypress.ScreenshotOptions> = {}): void {
  // Expand layout so fullPage captures all content (app has height:100vh + overflow-y:auto)
  // Only override height — do NOT remove overflow-x:hidden or horizontal scrollbars appear.
  // Force synchronous reflow via offsetHeight read so dark screenshot sees the new height.
  cy.document().then((doc) => {
    const s = doc.createElement("style");
    s.id = "ux-fullpage-layout";
    s.textContent = [
      ".app { height: auto !important; min-height: 100vh !important; }",
      ".app-main { height: auto !important; overflow: visible !important; overflow-x: hidden !important; }",
      "html, body, #root { height: auto !important; }",
      ".wizard-step { opacity: 1 !important; transform: none !important; }",
      ".wizard-content-v2 > * { opacity: 1 !important; }",
      ".wizard-content-v2 > * > * > * { opacity: 1 !important; transform: none !important; }",
    ].join(" ");
    doc.head.appendChild(s);
    void doc.body.offsetHeight;
  });
  cy.document().then(() => {});
  cy.wait(500);
  cy.screenshot(`${name}__dark`, { ...SCR_OPTS, ...opts });
  injectLightMode();
  cy.screenshot(`${name}__light`, { ...SCR_OPTS, ...opts });
  removeLightMode();
  cy.document().then((doc) => {
    doc.getElementById("ux-fullpage-layout")?.remove();
  });
}

// =============================================================================
// TESTS
// =============================================================================

// Prevent uncaught exceptions (Promise rejections, confirm dialogs, etc.) from failing tests
// These are screenshot-documentation tests, not functional assertion tests
Cypress.on('uncaught:exception', () => false);

describe("UX Screenshots — App-Workflow Dokumentation", () => {
  // Standard-Intercepts für alle Tests
  beforeEach(() => {
    cy.intercept("GET", "/api/devices", { body: { devices: MOCK_DEVICES } }).as("getDevices");
    cy.intercept("GET", `/api/presets/${DEVICE_ID_1}`, {
      body: MOCK_PRESETS_MIXED,
    }).as("getPresetsDevice1");
    cy.intercept("GET", `/api/presets/${DEVICE_ID_2}`, { body: [] }).as("getPresetsDevice2");
    cy.intercept("GET", "/api/settings/manual-ips", { body: MOCK_MANUAL_IPS }).as("getManualIPs");
    cy.intercept("POST", "/api/settings/manual-ips", { statusCode: 200, body: {} });
    cy.intercept("DELETE", "/api/settings/manual-ips/*", { statusCode: 200, body: {} });
    cy.intercept("POST", "/api/devices/sync-stream*", {
      statusCode: 409,
      body: { detail: "Discovery already in progress" },
    });
    cy.intercept("GET", "/api/devices/discover/stream*", {
      statusCode: 200,
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
      body: "event: error\ndata: {\"message\":\"No devices found\"}\n\n",
    });
    cy.intercept("DELETE", "/api/devices", { statusCode: 200, body: { count: 0 } });
    cy.intercept("POST", "/api/presets/set", { statusCode: 200, body: { message: "OK" } });
    cy.intercept("DELETE", "/api/presets/*", { statusCode: 200, body: { message: "OK" } });
    cy.intercept("GET", "/api/presets/*/sync", { statusCode: 200, body: { message: "Synced" } });
    cy.intercept("POST", "/api/presets/*/sync", { statusCode: 200, body: { message: "Synced" } });
    // Wizard routes
    cy.intercept("POST", "/api/wizard/**", { statusCode: 200, body: { status: "ok" } });
    cy.intercept("GET", "/api/wizard/**", { statusCode: 200, body: { status: "ok" } });
    // RadioBrowser
    cy.intercept("GET", "**/radiobrowser*/**", { body: [] });
    cy.intercept("GET", "**/radio-browser*/**", { body: [] });
  });

  // ===========================================================================
  // 01 — Welcome / EmptyState
  // ===========================================================================

  describe("01 — Welcome / EmptyState", () => {
    beforeEach(() => {
      // Keine Geräte → EmptyState wird angezeigt
      cy.intercept("GET", "/api/devices", { body: [] }).as("getDevicesEmpty");
    });

    it("01a — Vollseite: Initialzustand", () => {
      cy.visit("/welcome");
      cy.wait(800);
      screenshotBoth("01a_welcome_initial-state");
    });

    it("01b — Discover-Button: Normal + Fokus", () => {
      cy.visit("/welcome");
      cy.wait(600);

      cy.get('[data-test="discover-button"]').should("be.visible");
      scrFull("01b_welcome_discover-button__normal__dark");
      injectLightMode();
      scrFull("01b_welcome_discover-button__normal__light");
      removeLightMode();

      cy.get('[data-test="discover-button"]').focus();
      scrFull("01b_welcome_discover-button__focused__dark");
      injectLightMode();
      scrFull("01b_welcome_discover-button__focused__light");
      removeLightMode();
    });

    it("01c — Discover-Button: Aktiver Ladevorgang", () => {
      // Simuliert laufenden Discovery-Stream (SSE antwortet sofort mit data)
      cy.intercept("GET", "/api/devices/discover/stream*", {
        delay: 5000,
        statusCode: 200,
        headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
        body: "event: started\ndata: {}\n\n",
      }).as("streamStarted");

      cy.visit("/welcome");
      cy.wait(500);
      cy.get('[data-test="discover-button"]').click();
      cy.wait(600);
      scrFull("01c_welcome_discovering-in-progress__dark");
      injectLightMode();
      scrFull("01c_welcome_discovering-in-progress__light");
      removeLightMode();
    });

    it("01d — Manuelle IP Sektion: Details geöffnet", () => {
      cy.visit("/welcome");
      cy.wait(500);

      cy.get("details").should("exist").then(($details) => {
        if (!$details.attr("open")) {
          cy.get("details summary").click();
        }
      });
      cy.wait(400);
      screenshotBoth("01d_welcome_manual-ip-section__expanded");
    });

    it("01e — Manuelle IP Modal: Geöffnet", () => {
      cy.visit("/welcome");
      cy.wait(500);

      cy.get("details").then(($details) => {
        if (!$details.attr("open")) cy.get("details summary").click();
      });
      cy.get("body").then(($body) => {
        if ($body.find('[data-test="manual-add-button"]').length > 0) {
          cy.get('[data-test="manual-add-button"]').scrollIntoView().click({ force: true });
          cy.wait(600);
          if ($body.find('[data-test="modal-content"]').length > 0) {
            screenshotBoth("01e_welcome_manual-ip-modal__open");
          } else {
            scrFull("01e_welcome_manual-ip-modal__open__dark");
            injectLightMode();
            scrFull("01e_welcome_manual-ip-modal__open__light");
            removeLightMode();
          }
        } else {
          cy.log("manual-add-button not found — taking fallback screenshot");
          screenshotBoth("01e_welcome_manual-ip-modal__no-button");
        }
      });
    });

    it("01f — Mobile (375Ã—812): Vollseite", () => {
      cy.viewport(375, 812);
      cy.visit("/welcome");
      cy.wait(800);
      screenshotBoth("01f_welcome_mobile-375px__full");
    });
  });

  // ===========================================================================
  // 02 — Presets-Seite (RadioPresets)
  // ===========================================================================

  describe("02 — Presets-Seite", () => {
    it("02a — Vollseite: Gemischte Presets (3 belegt, 3 leer)", () => {
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(600);
      screenshotBoth("02a_presets_full-page__mixed-presets");
    });

    it("02b — Vollseite: Alle Presets leer", () => {
      cy.intercept("GET", `/api/presets/${DEVICE_ID_1}`, { body: MOCK_PRESETS_EMPTY });
      cy.intercept("GET", `/api/presets/${DEVICE_ID_2}`, { body: MOCK_PRESETS_EMPTY });

      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(600);
      screenshotBoth("02b_presets_full-page__all-empty");
    });

    it("02c — Device-Card / Swiper: Gerät 1", () => {
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(600); // Allow framer-motion initial animation to complete

      // Screenshot whole page (device card is inside swiper)
      screenshotBoth("02c_presets_device-card__device-1");

      // Gerät wechseln — use body.then() to avoid cy.get() timeout
      cy.get("body").then(($body) => {
        const $btn = $body.find("[data-test='device-next']");
        if ($btn.length > 0 && !$btn.prop("disabled")) {
          cy.get("[data-test='device-next']").click();
          cy.wait(400);
          screenshotBoth("02c_presets_device-card__device-2");
        } else {
          cy.log("device-next not found or disabled — skipping device-2 screenshot");
        }
      });
    });

    it("02d — Preset-Button: Alle Status-Varianten", () => {
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(800);

      // Vollständiges Preset-Grid (belegt + leer + Cloud-Badge)
      scrFull("02d_presets_preset-grid__all-states__dark");
      injectLightMode();
      scrFull("02d_presets_preset-grid__all-states__light");
      removeLightMode();

      // Fokus/Hover-States: nur wenn Elemente vorhanden (inside overflow:hidden, non-blocking)
      cy.get("body").then(($body) => {
        if ($body.find(".preset-play").length > 0) {
          cy.get(".preset-play").first().focus();
          scrFull("02d_presets_preset-button__assigned-focused__dark");
          injectLightMode();
          scrFull("02d_presets_preset-button__assigned-focused__light");
          removeLightMode();
        }
      });
      cy.get("body").then(($body) => {
        if ($body.find(".preset-empty").length > 0) {
          cy.get(".preset-empty").first().focus();
          scrFull("02d_presets_preset-button__empty-focused__dark");
          injectLightMode();
          scrFull("02d_presets_preset-button__empty-focused__light");
          removeLightMode();
        }
      });
      cy.get("body").then(($body) => {
        if ($body.find(".preset-clear").length > 0) {
          cy.get(".preset-clear").first().trigger("mouseover");
          scrFull("02d_presets_preset-button__clear-hover__dark");
          injectLightMode();
          scrFull("02d_presets_preset-button__clear-hover__light");
          removeLightMode();
        }
      });
    });

    it("02e — Lautstärke-Regler (Volume Slider)", () => {
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(600);

      // Use body.then() to avoid timeout if element is inside overflow:hidden container
      cy.get("body").then(($body) => {
        if ($body.find(".volume-slider").length > 0) {
          screenshotBoth("02e_presets_volume-slider__normal");
          if ($body.find(".volume-mute").length > 0) {
            cy.get(".volume-mute").click();
            cy.wait(200);
            scrFull("02e_presets_volume-slider__muted__dark");
            injectLightMode();
            scrFull("02e_presets_volume-slider__muted__light");
            removeLightMode();
          }
        } else {
          cy.log("volume-slider not in DOM — taking full-page fallback screenshot");
          screenshotBoth("02e_presets_volume-slider__full-page-fallback");
        }
      });
    });

    it("02f — RadioSearch Modal: Geöffnet", () => {
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(600);

      cy.intercept("GET", "/api/radio-browser*", { body: [] });
      cy.intercept("GET", "/radiobrowser*", { body: [] });

      // Auf leeren Preset klicken — .preset-empty ist der <button> in leerem .preset-button
      cy.get("body").then(($body) => {
        if ($body.find(".preset-empty").length > 0) {
          cy.get(".preset-empty").eq(0).scrollIntoView().click();
          cy.wait(600);
          // Modal is position:fixed — fullPage capture duplicates it in every viewport
          // chunk. Use viewport-only capture to get a single clean modal screenshot.
          screenshotViewport("02f_presets_radio-search-modal__open");
        } else {
          cy.log("No empty presets found — skipping modal screenshot");
          scrFull("02f_presets_radio-search-modal__no-empty-preset__dark");
        }
      });
    });

    it("02g — Navigation-Bar: Normal + aktive States", () => {
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(600);

      // Use body.then() to avoid timeout — Navigation only renders when devices.length > 0
      cy.get("body").then(($body) => {
        if ($body.find("nav.nav").length > 0) {
          scrFull("02g_navigation__presets-active__dark");
          injectLightMode();
          scrFull("02g_navigation__presets-active__light");
          removeLightMode();
          if ($body.find(".nav-link").length > 0) {
            cy.get(".nav-link").last().focus();
            scrFull("02g_navigation__settings-focused__dark");
            injectLightMode();
            scrFull("02g_navigation__settings-focused__light");
            removeLightMode();
          }
        } else {
          cy.log("nav.nav not in DOM — taking full-page fallback screenshot");
          scrFull("02g_navigation__not-found__dark");
        }
      });
    });

    it("02h — Mobile (375Ã—812): Vollseite", () => {
      cy.viewport(375, 812);
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(600);
      screenshotBoth("02h_presets_mobile-375px__full");
    });

    it("02i — Tablet (768Ã—1024): Vollseite", () => {
      cy.viewport(768, 1024);
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(600);
      screenshotBoth("02i_presets_tablet-768px__full");
    });

    it("02j \u2013 Widescreen (1260px): Vollseite", () => {
      // cy.viewport(1920) legt nur den CSS-Layout-Kontext auf 1920px fest,
      // das physische Cypress-Fenster bleibt ~1262px breit. Zentrierte Container
      // (z.B. max-width:1200px + margin:auto) haben dann einen linken Rand von
      // (1920-1200)/2 = 360px \u2014 im 1262px-Screenshot wirkt das rechtsb\u00fcndig.
      // 1260px ist die gr\u00f6\u00dfte Breite, bei der Cypress korrekt zentriert rendern kann.
      cy.viewport(1260, 900);
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(600);
      screenshotBoth("02j_presets_widescreen-1920px__full");
    });
  });

  // ===========================================================================
  // 03 — Settings-Seite
  // ===========================================================================

  describe("03 — Settings-Seite", () => {
    it("03a — Vollseite: Mit manuellen IPs", () => {
      cy.visit("/settings");
      cy.wait(1000);
      screenshotBoth("03a_settings_full-page__with-ips");
    });

    it("03b — Vollseite: Keine manuellen IPs", () => {
      cy.intercept("GET", "/api/settings/manual-ips", { body: [] });
      cy.visit("/settings");
      cy.wait(1000);
      screenshotBoth("03b_settings_full-page__empty-ips");
    });

    it("03c — IP-Eingabe-Formular: Fokus", () => {
      cy.visit("/settings");
      cy.wait(1500); // Wait for Settings to load (framer-motion + React Query)

      cy.get("body").then(($body) => {
        if ($body.find(".ip-input").length > 0) {
          cy.get(".ip-input").first().focus();
          screenshotBoth("03c_settings_add-ip-form__focused");
        } else {
          cy.log("ip-input not in DOM — taking fallback screenshot");
          scrFull("03c_settings_ip-input__not-found__dark");          injectLightMode();
          scrFull("03c_settings_ip-input__not-found__light");
          removeLightMode();        }
      });
    });

    it("03d — IP-Eingabe-Formular: Validierungsfehler", () => {
      cy.visit("/settings");
      cy.wait(1500); // Wait for Settings to load (framer-motion + React Query)

      cy.get("body").then(($body) => {
        if ($body.find(".ip-input").length > 0) {
          cy.get(".ip-input").first().type("dies-ist-keine-ip");
          cy.get("form.ip-add-form").submit();
          cy.wait(400);
          screenshotBoth("03d_settings_add-ip-form__validation-error");
        } else {
          cy.log("ip-input not in DOM — taking fallback screenshot");
          scrFull("03d_settings_ip-input__not-found__dark");          injectLightMode();
          scrFull("03d_settings_ip-input__not-found__light");
          removeLightMode();        }
      });
    });

    it("03e — IP-Eintrag: Delete-Button Hover", () => {
      cy.visit("/settings");
      cy.wait(1500); // Wait for Settings to load (framer-motion + React Query)

      cy.get("body").then(($body) => {
        if ($body.find(".btn-delete").length > 0) {
          cy.get(".btn-delete").first().trigger("mouseover");
          cy.wait(200);
          scrFull("03e_settings_ip-entry__delete-hover__dark");
          injectLightMode();
          scrFull("03e_settings_ip-entry__delete-hover__light");
          removeLightMode();
        } else {
          cy.log("No delete buttons found (no manual IPs) — taking fallback screenshot");
          scrFull("03e_settings_ip-entry__no-entries__dark");          injectLightMode();
          scrFull("03e_settings_ip-entry__no-entries__light");
          removeLightMode();        }
      });
    });

    it("03f — Mobile (375Ã—812): Vollseite", () => {
      cy.viewport(375, 812);
      cy.visit("/settings");
      cy.wait(1000);
      screenshotBoth("03f_settings_mobile-375px__full");
    });
  });

  // ===========================================================================
  // 04 — Setup Wizard
  // ===========================================================================

  describe("04 — Setup Wizard", () => {
    it("04a — Wizard: Start mit vorselektiertem Gerät (Step 1)", () => {
      cy.visit(`/setup-wizard?deviceId=${DEVICE_ID_1}`);
      cy.wait("@getDevices");
      cy.get(".setup-wizard-page-v2", { timeout: 10000 }).should("exist");
      screenshotBoth("04a_wizard_start__device-preselected");
    });

    it("04e — Wizard: Kein Gerät vorhanden (EmptyState)", () => {
      cy.intercept("GET", "/api/devices", { body: [] }).as("getDevicesEmpty");
      cy.visit("/setup-wizard");
      cy.wait("@getDevicesEmpty");
      cy.get(".wizard-empty-state", { timeout: 4000 }).should("be.visible");
      screenshotBoth("04e_wizard_empty-state__no-devices");
    });

    it("04f — Mobile (375x812): Wizard Step 1", () => {
      cy.viewport(375, 812);
      cy.visit(`/setup-wizard?deviceId=${DEVICE_ID_1}`);
      cy.wait("@getDevices");
      cy.get(".setup-wizard-page-v2", { timeout: 10000 }).should("exist");
      screenshotBoth("04f_wizard_mobile-375px__step-1");
    });
  });

  // ===========================================================================
  // 05 — Lade- und Fehlerzustände
  // ===========================================================================

  describe("05 — Lade- und Fehlerzustände", () => {
    it("05a — App: Initialer Ladezustand", () => {
      // Verzögerte API-Antwort → Ladeanimation nachweislich sichtbar
      cy.intercept("GET", "/api/devices", (req) => {
        req.reply({ delay: 3000, body: MOCK_DEVICES });
      }).as("getDevicesDelayed");

      cy.visit("/");
      cy.wait(300);
      scrFull("05a_app_loading-state__dark");
      injectLightMode();
      scrFull("05a_app_loading-state__light");
      removeLightMode();
    });

    it("05b — App: Fehler beim Laden der Geräte", () => {
      cy.intercept("GET", "/api/devices", {
        statusCode: 500,
        body: { detail: "Internal Server Error" },
      });
      cy.visit("/");
      cy.wait(1500);
      screenshotBoth("05b_app_error-state__device-load-failed");
    });

    it("05c — Presets: Ladezustand", () => {
      // Verzögerte Preset-Antwort → Ladeanimation sichtbar
      cy.intercept("GET", `/api/presets/${DEVICE_ID_1}`, (req) => {
        req.reply({ delay: 3000, body: MOCK_PRESETS_MIXED });
      }).as("getPresetsLoading");

      cy.visit("/");
      cy.wait(600);
      scrFull("05c_presets_loading-state__dark");
      injectLightMode();
      scrFull("05c_presets_loading-state__light");
      removeLightMode();
    });

    it("05d — Toast: Erfolgs-Nachricht", () => {
      cy.visit("/settings");
      cy.wait(1500); // Wait for Settings to load (framer-motion + React Query)

      cy.intercept("POST", "/api/settings/manual-ips", {
        statusCode: 200,
        body: {},
      }).as("addIPSuccess");

      cy.get("body").then(($body) => {
        if ($body.find(".ip-input").length > 0) {
          cy.get(".ip-input").first().type("192.168.1.200");
          cy.get("form.ip-add-form").submit();
          cy.wait(500);
          scrFull("05d_toast_success__dark");
          injectLightMode();
          scrFull("05d_toast_success__light");
          removeLightMode();
        } else {
          cy.log("ip-input not in DOM \u2014 taking fallback screenshot");
          scrFull("05d_toast__ip-input-not-found__dark");
          injectLightMode();
          scrFull("05d_toast__ip-input-not-found__light");
          removeLightMode();
        }
      });
    });
  });

  // ===========================================================================
  // 06 — Komponenten-Isolierung
  // ===========================================================================

  describe("06 — Komponenten-Isolierung", () => {
    it("06a — Preset-Grid: 6 Buttons (gemischt, Cloud-Badge)", () => {
      cy.visit("/");
      cy.wait(1200);

      scrFull("06a_component_preset-grid__mixed__dark");
      injectLightMode();
      scrFull("06a_component_preset-grid__mixed__light");
      removeLightMode();
    });

    it("06b — Lautstärke-Regler: Alle Positionen", () => {
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(800);

      // Use body.then() to avoid timeout — volume-input may be inside overflow:hidden
      cy.get("body").then(($body) => {
        if ($body.find("input[type='range'].volume-input").length > 0) {
          screenshotBoth("06b_component_volume-slider__default");
          cy.get("input[type='range'].volume-input").invoke("val", "0").trigger("input").trigger("change");
          cy.wait(200);
          scrFull("06b_component_volume-slider__at-0__dark");
          injectLightMode();
          scrFull("06b_component_volume-slider__at-0__light");
          removeLightMode();
          cy.get("input[type='range'].volume-input").invoke("val", "100").trigger("input").trigger("change");
          cy.wait(200);
          scrFull("06b_component_volume-slider__at-100__dark");
          injectLightMode();
          scrFull("06b_component_volume-slider__at-100__light");
          removeLightMode();
        } else {
          cy.log("volume-input not in DOM — taking full-page fallback screenshot");
          screenshotBoth("06b_component_volume-slider__full-page-fallback");
        }
      });
    });

    it("06c — Gerät-Swiper: Indikator-Punkte (3 Geräte simuliert)", () => {
      // Füge drittes Mock-Gerät hinzu
      cy.intercept("GET", "/api/devices", {
        body: [
          ...MOCK_DEVICES,
          {
            device_id: "C3D4E5F6A1B2",
            ip: "192.168.1.102",
            name: "Bose SoundTouch Wave",
            model: "SoundTouch Wave",
            firmware_version: "27.0.0.00000.00",
            mac_address: "C3:D4:E5:F6:A1:B2",
            last_seen: NOW,
          },
        ],
      });

      cy.visit("/");
      cy.wait(1200);
      screenshotBoth("06c_component_device-swiper__3-devices");
    });

    it("06d — Leer-Zustand (EmptyState Komponente)", () => {
      cy.intercept("GET", "/api/devices", { body: [] });
      cy.visit("/welcome");
      cy.wait(800);
      screenshotBoth("06d_component_empty-state__standalone");
    });

    it("06e — Setup-Badge auf Gerät", () => {
      cy.visit("/");
      cy.wait("@getDevices");
      cy.wait(800);

      // Use body.then() to avoid cy.get() timeout if badge is inside overflow:hidden
      cy.get("body").then(($body) => {
        if ($body.find(".setup-badge").length > 0) {
          screenshotBoth("06e_component_setup-badge__visible");
        } else {
          cy.log("Setup-Badge nicht im DOM — skipping");
          scrFull("06e_component_setup-badge__not-present__dark");
        }
      });
    });
  });

  // ===========================================================================
  // 07 — Viewport-Matrix (Responsive Design Audit)
  // ===========================================================================

  describe("07 — Viewport-Matrix alle Seiten", () => {
    const VIEWPORTS = [
      { name: "mobile-375", width: 375, height: 812 },
      { name: "tablet-768", width: 768, height: 1024 },
      { name: "desktop-1280", width: 1280, height: 800 },
      { name: "wide-1920", width: 1920, height: 1080 },
    ] as const;

    VIEWPORTS.forEach(({ name, width, height }) => {
      it(`07_${name} — Presets-Seite`, () => {
        cy.viewport(width, height);
        cy.visit("/");
        cy.wait(1200);
        scrFull(`07_viewport_${name}__presets__dark`);
        injectLightMode();
        scrFull(`07_viewport_${name}__presets__light`);
        removeLightMode();
      });

      it(`07_${name} \u2014 Settings-Seite`, () => {
        cy.viewport(width, height);
        cy.visit("/settings");
        cy.wait(1000);
        scrFull(`07_viewport_${name}__settings__dark`);
        injectLightMode();
        scrFull(`07_viewport_${name}__settings__light`);
        removeLightMode();
      });
    });
  });
});
