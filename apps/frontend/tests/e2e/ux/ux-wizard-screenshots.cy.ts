// Make this file a TypeScript module to avoid duplicate-declaration
// conflicts with shared helpers in ux-workflow-screenshots.cy.ts
export {};

/**
 * UX Screenshots — Setup Wizard (Vollständiger Durchlauf)
 *
 * Jeden Schritt des Setup-Wizards wird vollständig durchlaufen mit
 * gemockten Backend-Antworten (kein echtes Gerät nötig).
 *
 * Abgedeckte Szenarien:
 *   HAPPY PATH : Jeder Schritt mit Erfolgs-Response (dark + light)
 *   ERROR PATH : Jeden relevanten Fehlerfall (Port-Check fehl, Backup fehl,
 *                Config fehl, Hosts fehl)
 *
 * Schritte des manuellen Wizards:
 *   Step 0: Modus-Auswahl
 *   Step 1: USB-Vorbereitung
 *   Step 2: PowerCycle + SSH-Port-Check
 *   Step 3: SSH-Entscheidung (innerhalb Step 2)
 *   Step 4: Backup (optional)
 *   Step 5: Konfiguration ändern
 *   Step 6: Hosts-Datei ändern
 *   Step 7: Verifikation
 *   Step 8: Abschluss
 *
 * Output: tests/e2e/screenshots/ux/ (Dateinamen: wiz_{step}_{beschreibung}__{dark|light}.png)
 *
 * Aufruf:
 *   npm run screenshots  (oder mit -- --spec "tests/e2e/ux/ux-wizard-screenshots.cy.ts")
 */

// =============================================================================
// MOCK DATA
// =============================================================================

const DEVICE = {
  device_id: "A1B2C3D4E5F6",
  ip: "192.168.1.100",
  name: "Bose SoundTouch 10",
  model: "SoundTouch 10",
  firmware_version: "29.0.3.46291.53",
  mac_address: "A1:B2:C3:D4:E5:F6",
  last_seen: new Date().toISOString(),
};

const BACKUP_SUCCESS = {
  success: true,
  message: "Backup erstellt",
  volumes: [
    { volume: "/nv", path: "/usb/backups/nv.tar.gz", size_mb: 2.1, duration_seconds: 3 },
    { volume: "/mnt/nv", path: "/usb/backups/mnt_nv.tar.gz", size_mb: 0.4, duration_seconds: 1 },
  ],
  total_size_mb: 2.5,
  total_duration_seconds: 4,
};

const CONFIG_SUCCESS = {
  success: true,
  action: "modified",
  old_url: "bmx.bose.com",
  new_url: "192.168.1.11",
  backup_path: "/usb/backups/config_backup.xml",
  diff: "- bmx.bose.com\n+ 192.168.1.11",
  message: "Konfiguration erfolgreich geändert",
};

const HOSTS_SUCCESS = {
  success: true,
  action: "modified",
  added_entries: 7,
  backup_path: "/usb/backups/hosts_backup",
  diff:
    "+ 192.168.1.11 bose.vtuner.com\n+ 192.168.1.11 streaming.bose.com\n+ 192.168.1.11 update.bose.com",
  message: "Hosts-Datei erfolgreich geändert",
};

const VERIFY_SUCCESS = {
  success: true,
  domain: "bose.vtuner.com",
  resolved_ip: "192.168.1.11",
  matches_expected: true,
  message: "bose.vtuner.com → 192.168.1.11 ✓",
};

// =============================================================================
// SCREENSHOT HELPERS
// =============================================================================

const SCR_OPTS = { overwrite: true, disableTimersAndAnimations: true, capture: "fullPage" } as const;

function injectLightMode(): void {
  cy.document().then((doc) => {
    if (doc.getElementById("ux-light-override")) return;
    const style = doc.createElement("style");
    style.id = "ux-light-override";
    style.textContent = `
      :root {
        --color-bg-dark:        #f8f9fa !important;
        --color-bg-card:        #ffffff !important;
        --color-bg-input:       #ffffff !important;
        --color-bg-hover:       #e9ecef !important;
        --color-text-primary:   #212529 !important;
        --color-text-secondary: #6c757d !important;
        --color-border:         #dee2e6 !important;
        --color-accent:         #0055aa !important;
        --text-primary:         #212529 !important;
        --surface-color:        #ffffff !important;
        --border-color:         #dee2e6 !important;
      }
      body, html, .app, .app-main, #root {
        background: #f8f9fa !important;
        color: #212529 !important;
      }
      .app-header, .nav, .nav-container {
        background: #e9ecef !important;
        border-bottom: 1px solid #dee2e6 !important;
      }
      .wizard-container, .wizard-card, .setup-wizard-page-v2,
      .mode-selector-container, .wizard-step-container,
      .step-card, .power-cycle-check, .ssh-risk-assessment,
      .backup-step, .config-step, .hosts-step, .verify-step,
      .completion-step {
        background: #ffffff !important;
        color: #212529 !important;
        border: 1px solid #dee2e6 !important;
      }
      .mode-guided, .mode-manual, .mode-card {
        background: #ffffff !important;
        color: #212529 !important;
        border: 1px solid #ced4da !important;
      }
      .mode-guided.mode-card.selected, .mode-manual.mode-card.selected {
        border-color: #0055aa !important;
        background: #e8f0fe !important;
      }
      input, textarea, select, .config-input {
        background: #ffffff !important;
        color: #212529 !important;
        border: 1px solid #ced4da !important;
      }
      button, .btn {
        color: #212529 !important;
        border-color: #ced4da !important;
      }
      .btn-primary, button.primary, .weiter-button {
        background: #0055aa !important;
        color: #ffffff !important;
      }
      .progress-tracker, .progress-step {
        color: #495057 !important;
      }
    `;
    doc.head.appendChild(style);
  });
}

function removeLightMode(): void {
  cy.document().then((doc) => {
    doc.getElementById("ux-light-override")?.remove();
  });
}

function screenshotBoth(name: string): void {
  // Expand layout so fullPage captures all content (app has height:100vh + overflow-y:auto)
  // Only override height — do NOT remove overflow-x:hidden or horizontal scrollbars appear.
  // Force synchronous reflow via offsetHeight read so dark screenshot sees the new height.
  cy.document().then((doc) => {
    const s = doc.createElement("style");
    s.id = "ux-fullpage-layout";
    // Remove the internal scroll container so Chrome's captureBeyondViewport
    // captures the full document, not just the viewport-height app-main slice.
    // overflow: visible resets both axes; overflow-x: hidden then restores it
    // so no horizontal scrollbar appears from wide code blocks.
    // #root has height:100% in index.css — override to auto so it grows with content.
    s.textContent = [
      ".app { height: auto !important; min-height: 100vh !important; }",
      ".app-main { height: auto !important; overflow: visible !important; overflow-x: hidden !important; }",
      "html, body, #root { height: auto !important; }",
      // framer-motion v12 uses CSS transitions for opacity/transform.
      // disableTimersAndAnimations: true freezes CSS transitions BEFORE they
      // complete, leaving elements at initial opacity:0. Force final state here.
      ".wizard-step { opacity: 1 !important; transform: none !important; }",
      ".wizard-content-v2 > * { opacity: 1 !important; }",
      ".wizard-content-v2 > * > * > * { opacity: 1 !important; transform: none !important; }",
    ].join(" ");
    doc.head.appendChild(s);
    void doc.body.offsetHeight; // force synchronous reflow
  });
  // Extra tick so React flushes any async state updates before the screenshot
  cy.document().then(() => {});
  // Wait for framer-motion (transition.duration: 0.3s) to complete BEFORE
  // disableTimersAndAnimations freezes the CSS transitions on screenshot.
  cy.wait(500);
  cy.screenshot(`${name}__dark`, SCR_OPTS);
  injectLightMode();
  cy.screenshot(`${name}__light`, SCR_OPTS);
  removeLightMode();
  cy.document().then((doc) => {
    doc.getElementById("ux-fullpage-layout")?.remove();
  });
}

// =============================================================================
// SHARED MOCK SETUP
// =============================================================================

/**
 * Sets up all backend intercepts needed for the wizard happy path.
 * Individual tests can override specific intercepts before cy.visit().
 */
function setupWizardMocks() {
  cy.intercept("GET", "/api/devices", {
    statusCode: 200,
    body: { devices: [DEVICE] },
  }).as("getDevices");

  cy.intercept("GET", "/api/settings/manual-ips", { body: [] });

  cy.intercept("POST", "/api/setup/wizard/check-ports", {
    statusCode: 200,
    body: { success: true, has_ssh: true, has_telnet: false, message: "SSH verfügbar" },
  }).as("checkPorts");

  cy.intercept("POST", "/api/setup/ssh/enable-permanent", {
    statusCode: 200,
    body: { success: true, permanent_enabled: false, message: "SSH bleibt temporär aktiv." },
  }).as("enableSSH");

  cy.intercept("POST", "/api/setup/wizard/backup", {
    statusCode: 200,
    body: BACKUP_SUCCESS,
  }).as("createBackup");

  cy.intercept("POST", "/api/setup/wizard/modify-config", {
    statusCode: 200,
    body: CONFIG_SUCCESS,
  }).as("modifyConfig");

  cy.intercept("POST", "/api/setup/wizard/modify-hosts", {
    statusCode: 200,
    body: HOSTS_SUCCESS,
  }).as("modifyHosts");

  cy.intercept("POST", "/api/setup/wizard/verify-redirect", {
    statusCode: 200,
    body: VERIFY_SUCCESS,
  }).as("verifyRedirect");

  cy.intercept("POST", "/api/setup/wizard/reboot-device", {
    statusCode: 200,
    body: { success: true, message: "Neustart eingeleitet" },
  }).as("rebootDevice");

  cy.intercept("POST", "/api/setup/wizard/finalize", {
    statusCode: 200,
    body: {
      success: true,
      uuid: "TEST-UUID-1234",
      had_uuid: false,
      uuid_was_collision: false,
      sources_written: true,
      sources_backup_path: "/usb/backups/sources_backup.xml",
      system_config_written: true,
      message: "Device setup finalized successfully",
    },
  }).as("finalizeDevice");

  cy.intercept("POST", "/api/setup/wizard/verify-setup", {
    statusCode: 200,
    body: {
      success: true,
      checks: [
        { name: "ssh_accessible", passed: true, message: "SSH erreichbar", details: {} },
        { name: "sources_xml", passed: true, message: "Sources.xml korrekt", details: {} },
        { name: "uuid_set", passed: true, message: "UUID gesetzt", details: {} },
      ],
      passed_count: 3,
      failed_count: 0,
      message: "All checks passed",
    },
  }).as("verifySetup");

  // Intercept detect-strategy and server-info to prevent real backend calls
  // that could return proxy_available=true and hide the config modification button
  cy.intercept("GET", "/api/setup/wizard/detect-strategy", {
    statusCode: 200,
    body: {
      proxy_available: false,
      strategy: "bmx_and_hosts",
      message: "Standard-Strategie: BMX + Hosts",
    },
  }).as("detectStrategy");

  cy.intercept("GET", "/api/setup/wizard/server-info", {
    statusCode: 200,
    body: {
      server_url: "http://localhost:7778",
      server_ip: "127.0.0.1",
    },
  }).as("serverInfo");
}

/** Wait for wizard to be ready at Step 1 (mode selector was removed; wizard starts directly) */
function selectManualMode() {
  cy.get(".setup-wizard-page-v2", { timeout: 8000 }).should("exist");
  cy.contains("Setup-Assistent").click();
  cy.wait(400);
}

/** Complete USB Prep step: check all boxes → Weiter */
function completeUSBPrep() {
  cy.get('input[type="checkbox"]').each(($cb) => {
    cy.wrap($cb).check({ force: true });
  });
  cy.contains("button", /weiter/i).click({ force: true });
  cy.wait(300);
}

/** Complete PowerCycle+SSH step: run port check → select "nicht dauerhaft" → Weiter */
function completePowerCycleStep() {
  cy.contains("button", /jetzt prüfen/i, { timeout: 8000 }).click({ force: true });
  cy.wait("@checkPorts");
  // Decision cards appear once portsAvailable is true
  cy.get(".risk-decision-buttons", { timeout: 8000 }).should("exist");
  cy.get(".risk-card--temporary").click({ force: true });
  cy.contains("button", /weiter/i).click({ force: true });
  cy.wait(300);
}

/** Complete Backup step without running backup (skippable) */
function skipBackupStep() {
  cy.contains("button", /weiter/i, { timeout: 8000 }).should("not.be.disabled").click({ force: true });
  cy.wait(300);
}

/** Complete Config step: trigger modification → Weiter */
function completeConfigStep() {
  cy.contains("button", /konfiguration.*ndern/i, { timeout: 8000 }).click({ force: true });
  cy.contains(/bmx\.bose\.com|konfiguration.*geändert|erfolgreich/i, { timeout: 10000 }).should("exist");
  // Wait explicitly for "Weiter" to be enabled (isNextDisabled=false after successful modification)
  cy.contains("button", /weiter/i, { timeout: 8000 }).should("not.be.disabled").click();
  cy.wait(500);
}

/** Complete Hosts step: trigger modification → Weiter */
function completeHostsStep() {
  cy.contains("button", /hosts.*datei/i, { timeout: 8000 }).click({ force: true });
  cy.contains(/hosts.*geändert|einträge|erfolgreich/i, { timeout: 10000 }).should("exist");
  cy.contains("button", /weiter/i).click({ force: true });
  cy.wait(300);
}

// =============================================================================
// TESTS
// =============================================================================

Cypress.on("uncaught:exception", () => false);

/** Force German locale — CI defaults to English (navigator.language='en') */
function visitDe(url: string) {
  cy.visit(url, {
    onBeforeLoad(win) {
      win.localStorage.setItem("oct-lang", "de");
    },
  });
}

describe("UX Screenshots — Setup Wizard (Vollständiger Durchlauf)", () => {
  beforeEach(() => {
    setupWizardMocks();
  });

  // ===========================================================================
  // SCHRITT 0: Wizard-Start
  // ===========================================================================

  describe("Schritt 0 — Wizard-Start", () => {
    it("wiz_00a — Wizard-Start: Mit Gerät vorselektiert (Step 1)", () => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      cy.get(".setup-wizard-page-v2", { timeout: 8000 }).should("exist");
      screenshotBoth("wiz_00a_wizard-start__device-preselected");
    });

    it("wiz_00d — Wizard: Kein Gerät vorhanden (EmptyState)", () => {
      cy.intercept("GET", "/api/devices", { body: [] }).as("getDevicesEmpty");
      visitDe("/setup-wizard");
      cy.wait("@getDevicesEmpty");
      cy.get(".wizard-empty-state", { timeout: 6000 }).should("be.visible");
      screenshotBoth("wiz_00d_mode-selection__empty-state");
    });
  });

  // ===========================================================================
  // SCHRITT 1: USB-Vorbereitung (Manual Mode)
  // ===========================================================================

  describe("Schritt 1 — USB-Vorbereitung", () => {
    beforeEach(() => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      selectManualMode();
    });

    it("wiz_01a — USB-Vorbereitung: Initialzustand (Weiter gesperrt)", () => {
      // Before checking any boxes
      screenshotBoth("wiz_01a_usb-prep__initial-locked");
    });

    it("wiz_01b — USB-Vorbereitung: Alle Boxen angehakt (Weiter aktiv)", () => {
      cy.get('input[type="checkbox"]').each(($cb) => {
        cy.wrap($cb).check({ force: true });
      });
      cy.contains("button", /weiter/i).should("not.be.disabled");
      screenshotBoth("wiz_01b_usb-prep__all-checked-ready");
    });
  });

  // ===========================================================================
  // SCHRITT 2: PowerCycle + SSH-Port-Check
  // ===========================================================================

  describe("Schritt 2 — PowerCycle & SSH-Port-Check", () => {
    beforeEach(() => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      selectManualMode();
      completeUSBPrep();
    });

    it("wiz_02a — PowerCycle: Initialzustand (vor Port-Check)", () => {
      cy.contains("button", /jetzt prüfen/i, { timeout: 8000 }).should("exist");
      screenshotBoth("wiz_02a_powercycle__initial");
    });

    it("wiz_02b — PowerCycle: SSH verfügbar, SSH-Entscheidung sichtbar", () => {
      cy.contains("button", /jetzt prüfen/i, { timeout: 8000 }).click({ force: true });
      cy.wait("@checkPorts");
      cy.get(".power-cycle-status.success", { timeout: 6000 }).should("exist");
      screenshotBoth("wiz_02b_powercycle__ssh-available");
    });

    it("wiz_02c — PowerCycle: Dauerhaft-SSH gewählt (Weiter aktiv)", () => {
      cy.contains("button", /jetzt prüfen/i, { timeout: 8000 }).click({ force: true });
      cy.wait("@checkPorts");
      cy.get(".risk-card--permanent", { timeout: 6000 }).click({ force: true });
      cy.contains("button", /weiter/i).should("not.be.disabled");
      screenshotBoth("wiz_02c_powercycle__permanent-ssh-selected");
    });

    it("wiz_02d — PowerCycle: Temporär-SSH gewählt (Weiter aktiv)", () => {
      cy.contains("button", /jetzt prüfen/i, { timeout: 8000 }).click({ force: true });
      cy.wait("@checkPorts");
      cy.get(".risk-card--temporary", { timeout: 6000 }).click({ force: true });
      cy.contains("button", /weiter/i).should("not.be.disabled");
      screenshotBoth("wiz_02d_powercycle__temporary-ssh-selected");
    });

    it("wiz_02e — PowerCycle FEHLER: Kein SSH, kein Telnet", () => {
      cy.intercept("POST", "/api/setup/wizard/check-ports", {
        statusCode: 200,
        body: {
          success: false,
          has_ssh: false,
          has_telnet: false,
          message: "Keine Ports erreichbar – Gerät neu starten und erneut prüfen",
        },
      }).as("checkPortsFailed");

      cy.contains("button", /jetzt prüfen/i, { timeout: 8000 }).click({ force: true });
      cy.wait("@checkPortsFailed");
      cy.get(".power-cycle-status.error", { timeout: 6000 }).should("exist");
      screenshotBoth("wiz_02e_powercycle__error-no-ports");
    });
  });

  // ===========================================================================
  // SCHRITT 3: Backup (optional)
  // ===========================================================================

  describe("Schritt 3 — Backup", () => {
    beforeEach(() => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      selectManualMode();
      completeUSBPrep();
      completePowerCycleStep();
    });

    it("wiz_03a — Backup: Initialzustand (Weiter bereits aktiv)", () => {
      cy.contains(/backup/i, { timeout: 8000 }).should("exist");
      cy.contains("button", /weiter/i).should("not.be.disabled");
      screenshotBoth("wiz_03a_backup__initial-skippable");
    });

    it("wiz_03b — Backup: Erfolgreich durchgeführt", () => {
      cy.contains("button", /backup.*erstellen/i, { timeout: 8000 }).click({ force: true });
      cy.contains(/backup.*erstellt|nv|erfolgreich/i, { timeout: 10000 }).should("exist");
      screenshotBoth("wiz_03b_backup__success");
    });

    it("wiz_03c — Backup FEHLER: Backup fehlgeschlagen", () => {
      cy.intercept("POST", "/api/setup/wizard/backup", {
        statusCode: 500,
        body: {
          success: false,
          message: "Backup fehlgeschlagen: USB-Stick nicht gefunden",
          detail: "No USB drive mounted at /usb",
        },
      });

      cy.contains("button", /backup.*erstellen/i, { timeout: 8000 }).click({ force: true });
      cy.contains(/fehler|fehlgeschlagen|nicht gefunden|error/i, { timeout: 10000 }).should(
        "exist"
      );
      screenshotBoth("wiz_03c_backup__error-usb-not-found");
    });
  });

  // ===========================================================================
  // SCHRITT 4: Konfiguration ändern
  // ===========================================================================

  describe("Schritt 4 — Konfiguration ändern", () => {
    beforeEach(() => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      selectManualMode();
      completeUSBPrep();
      completePowerCycleStep();
      skipBackupStep();
    });

    it("wiz_04a — Konfiguration: Initialzustand", () => {
      cy.contains("button", /konfiguration.*ndern/i, { timeout: 8000 }).should("exist");
      screenshotBoth("wiz_04a_config__initial");
    });

    it("wiz_04b — Konfiguration: Erfolgreich geändert (zeigt alte + neue URL)", () => {
      cy.contains("button", /konfiguration.*ndern/i, { timeout: 8000 }).click({ force: true });
      cy.contains("bmx.bose.com", { timeout: 10000 }).should("exist");
      cy.contains("192.168.1.11").should("exist");
      screenshotBoth("wiz_04b_config__success-urls-visible");
    });

    it("wiz_04c — Konfiguration FEHLER: SSH-Verbindung fehlgeschlagen", () => {
      cy.intercept("POST", "/api/setup/wizard/modify-config", {
        statusCode: 500,
        body: {
          success: false,
          detail: "SSH connection timeout after 10s",
          message: "Konfiguration konnte nicht geändert werden: SSH-Verbindung fehlgeschlagen",
        },
      });

      cy.contains("button", /konfiguration.*ndern/i, { timeout: 8000 }).click({ force: true });
      cy.contains(/fehler|konnte nicht|fehlgeschlagen|error/i, { timeout: 10000 }).should(
        "exist"
      );
      screenshotBoth("wiz_04c_config__error-ssh-failed");
    });
  });

  // ===========================================================================
  // SCHRITT 5: Hosts-Datei ändern
  // ===========================================================================

  describe("Schritt 5 — Hosts-Datei ändern", () => {
    beforeEach(() => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      selectManualMode();
      completeUSBPrep();
      completePowerCycleStep();
      skipBackupStep();
      completeConfigStep();
    });

    it("wiz_05a — Hosts: Initialzustand", () => {
      cy.contains("button", /hosts.*datei/i, { timeout: 8000 }).should("exist");
      screenshotBoth("wiz_05a_hosts__initial");
    });

    it("wiz_05b — Hosts: Erfolgreich geändert (Diff sichtbar)", () => {
      cy.contains("button", /hosts.*datei/i, { timeout: 8000 }).click({ force: true });
      cy.contains(/hosts.*geändert|einträge.*hinzugefügt|7/i, { timeout: 10000 }).should(
        "exist"
      );
      screenshotBoth("wiz_05b_hosts__success-diff-visible");
    });

    it("wiz_05c — Hosts FEHLER: SSH-Verbindung fehlgeschlagen", () => {
      cy.intercept("POST", "/api/setup/wizard/modify-hosts", {
        statusCode: 500,
        body: {
          success: false,
          detail: "SSH connection refused",
          message: "Hosts-Datei konnte nicht geändert werden",
        },
      });

      cy.contains("button", /hosts.*datei/i, { timeout: 8000 }).click({ force: true });
      cy.contains(/fehler|konnte nicht|fehlgeschlagen|error/i, { timeout: 10000 }).should(
        "exist"
      );
      screenshotBoth("wiz_05c_hosts__error-ssh-refused");
    });
  });

  // ===========================================================================
  // SCHRITT 6: Verifikation
  // ===========================================================================

  describe("Schritt 6 — DNS-Verifikation", () => {
    beforeEach(() => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      selectManualMode();
      completeUSBPrep();
      completePowerCycleStep();
      skipBackupStep();
      completeConfigStep();
      completeHostsStep();
    });

    it("wiz_06a — Verifikation: Initialzustand (vor DNS-Check)", () => {
      cy.get(".setup-wizard-page-v2", { timeout: 8000 }).should("exist");
      cy.wait(600);
      screenshotBoth("wiz_06a_verification__initial");
    });

    it("wiz_06b — Verifikation: DNS-Check erfolgreich (IP stimmt überein)", () => {
      // First click "Finalize" to go through finalize/verify phases
      cy.contains("button", /abschließen|finalize/i, { timeout: 8000 }).click({
        force: true,
      });
      cy.wait("@finalizeDevice");
      cy.wait("@verifySetup");
      // Now the DNS test button should appear
      cy.contains("button", /tests jetzt ausführen|ausführen|verify/i, { timeout: 8000 }).click({
        force: true,
      });
      cy.contains(/192.168.1.11|bose.vtuner.com|\u2713|stimmt überein|verifiziert/i, {
        timeout: 10000,
      }).should("exist");
      screenshotBoth("wiz_06b_verification__dns-match-success");
    });

    it("wiz_06c — Verifikation FEHLER: DNS zeigt noch alte IP", () => {
      cy.intercept("POST", "/api/setup/wizard/verify-redirect", {
        statusCode: 200,
        body: {
          success: false,
          domain: "bose.vtuner.com",
          resolved_ip: "208.97.182.102",
          matches_expected: false,
          message: "bose.vtuner.com → 208.97.182.102 (erwartet: 192.168.1.11)",
        },
      });

      // First click "Finalize" to go through finalize/verify phases
      cy.contains("button", /abschließen|finalize/i, { timeout: 8000 }).click({
        force: true,
      });
      cy.wait("@finalizeDevice");
      cy.wait("@verifySetup");
      // Now the DNS test button should appear
      cy.contains("button", /tests jetzt ausführen|ausführen|verify/i, { timeout: 8000 }).click({
        force: true,
      });
      cy.contains(/208.97.182.102|stimmt nicht|fehlgeschlagen|mismatch/i, {
        timeout: 10000,
      }).should("exist");
      screenshotBoth("wiz_06c_verification__dns-mismatch-error");
    });

    it("wiz_06d — Verifikation: Neustart-Button sichtbar", () => {
      cy.contains("button", /neu.*start|reboot/i, { timeout: 8000 }).should("exist");
      screenshotBoth("wiz_06d_verification__reboot-button-visible");
    });

    it("wiz_06e — Verifikation: Nach Neustart-Klick", () => {
      cy.contains("button", /neu.*start|reboot/i, { timeout: 8000 }).click({ force: true });
      cy.wait(1000);
      screenshotBoth("wiz_06e_verification__reboot-initiated");
    });
  });

  // ===========================================================================
  // SCHRITT 7: Abschluss (Step 8 Completion)
  // ===========================================================================

  describe("Schritt 7 — Abschluss", () => {
    it("wiz_07a — Abschluss: Erfolgreicher Wizard-Durchlauf", () => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      selectManualMode();
      completeUSBPrep();
      completePowerCycleStep();
      skipBackupStep();
      completeConfigStep();
      completeHostsStep();

      // Navigate to completion (Step 7)
      cy.contains("button", /weiter/i, { timeout: 8000 }).click({ force: true });
      cy.wait(600);

      // Take screenshot of completion/verification step
      screenshotBoth("wiz_07a_completion__wizard-done");
    });
  });

  // ===========================================================================
  // MOBIL-ANSICHTEN (375px)
  // ===========================================================================

  describe("Mobil-Ansichten", () => {
    beforeEach(() => {
      cy.viewport(375, 812);
    });

    it("wiz_mob_a — Mobile: Wizard-Start (Step 1)", () => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      cy.get(".setup-wizard-page-v2", { timeout: 8000 }).should("exist");
      screenshotBoth("wiz_mob_a_wizard-start__mobile-375");
    });

    it("wiz_mob_b — Mobile: USB-Vorbereitung", () => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      selectManualMode();
      screenshotBoth("wiz_mob_b_usb-prep__mobile-375");
    });

    it("wiz_mob_c — Mobile: SSH-Port-Check (SSH verfügbar)", () => {
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}`);
      cy.wait("@getDevices");
      selectManualMode();
      completeUSBPrep();
      cy.contains("button", /jetzt prüfen/i, { timeout: 8000 }).click({ force: true });
      cy.wait("@checkPorts");
      cy.get(".power-cycle-status.success", { timeout: 6000 }).should("exist");
      screenshotBoth("wiz_mob_c_powercycle__ssh-available-mobile-375");
    });
  });
});
