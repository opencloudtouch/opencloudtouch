/**
 * E2E Tests: Wizard i18n — Translation Smoke Tests
 *
 * Verifies that all wizard step pages (Step 1–8) render translated strings
 * in the active language (English default + German switch).
 *
 * These are smoke tests, not full regression tests. Each test checks that
 * the most important visible strings are translated and not hardcoded German.
 */

const FRONTEND_BASE = "http://localhost:4173";

const MOCK_DEVICE = {
  device_id: "DEVICE_WOHNZIMMER",
  name: "Wohnzimmer",
  model: "SoundTouch 10",
  ip: "192.168.1.79",
  mac: "A4:15:88:AA:BB:CC",
  type: "soundtouch",
};

function setupWizardMocks() {
  cy.intercept("GET", "/api/devices", {
    statusCode: 200,
    body: { devices: [MOCK_DEVICE] },
  }).as("getDevices");

  cy.intercept("POST", "/api/setup/wizard/check-ports", {
    statusCode: 200,
    body: { success: true, has_ssh: true, has_telnet: false, message: "SSH available" },
  }).as("checkPorts");

  cy.intercept("POST", "/api/setup/wizard/backup", {
    statusCode: 200,
    body: {
      success: true,
      message: "Backup created",
      volumes: [],
      total_size_mb: 0,
      total_duration_seconds: 0,
      backup_path: "/usb/backups",
    },
  }).as("backup");

  cy.intercept("GET", "/api/setup/server-info", {
    statusCode: 200,
    body: { server_url: "http://192.168.1.100:7777" },
  }).as("serverInfo");

  cy.intercept("POST", "/api/setup/wizard/detect-strategy", {
    statusCode: 200,
    body: { proxy_available: false, strategy: "bmx_and_hosts", message: "No proxy detected" },
  }).as("detectStrategy");

  cy.intercept("POST", "/api/setup/wizard/modify-config", {
    statusCode: 200,
    body: { success: true, message: "Config modified", old_url: "https://streaming.bose.com", new_url: "http://192.168.1.100:7777" },
  }).as("modifyConfig");

  cy.intercept("POST", "/api/setup/wizard/modify-hosts", {
    statusCode: 200,
    body: { success: true, message: "Hosts modified", backup_path: "/etc/hosts.bak" },
  }).as("modifyHosts");

  cy.intercept("POST", "/api/setup/wizard/verify-redirect", {
    statusCode: 200,
    body: { success: true, resolved_ip: "192.168.1.100", expected_ip: "192.168.1.100", matches_expected: true, message: "OK" },
  }).as("verifyRedirect");
}

function navigateToWizard() {
  cy.visit(FRONTEND_BASE);
  cy.wait("@getDevices");
  cy.contains("Settings").click();
  cy.contains("Setup Wizard", { timeout: 5000 }).click();
}

// ─── English (default) ────────────────────────────────────────────────────────

describe("Wizard i18n — English (default)", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.visit(FRONTEND_BASE);
    cy.wait("@getDevices");
  });

  it("Step 1 (device selection) renders in English", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard`);
    cy.contains("Step 1").should("exist");
    cy.contains("Configure Device").should("exist");
    // No German strings visible
    cy.contains("Gerät konfigurieren").should("not.exist");
  });

  it("Step 2 (USB preparation) renders English title and descriptions", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=2&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.contains("Prepare USB drive").should("exist");
    cy.contains("USB_SOUNDTOUCH").should("exist");
    // Not German
    cy.contains("USB-Stick vorbereiten").should("not.exist");
  });

  it("Step 3 (power cycle) renders English title", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=3&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.contains("Restart device").should("exist");
    cy.contains("USB drive").should("exist");
    cy.contains("Gerät neu starten").should("not.exist");
  });

  it("Step 4 (backup) renders English title", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=4&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.contains("Create backup").should("exist");
    cy.contains("Backup erstellen").should("not.exist");
  });

  it("Step 5 (config modification) renders English title", () => {
    cy.wait("@serverInfo");
    cy.wait("@detectStrategy");
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=5&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.contains(/Modify configuration file|Reverse proxy detected/, { timeout: 5000 }).should("exist");
    cy.contains("Konfigurationsdatei ändern").should("not.exist");
  });

  it("Step 6 (hosts modification) renders English title and domain labels", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=6&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.contains("Modify hosts file").should("exist");
    cy.contains("Required").should("exist");
    cy.contains("Optional").should("exist");
    cy.contains("Hosts-Datei ändern").should("not.exist");
  });

  it("Step 7 (verification) renders English title", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=7&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.contains("Test configuration").should("exist");
    cy.contains("Konfiguration testen").should("not.exist");
  });

  it("Step 8 (completion) renders English title", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=8&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79&deviceName=Wohnzimmer`);
    cy.contains("Setup complete").should("exist");
    cy.contains("Setup abgeschlossen").should("not.exist");
  });

  it("navigation bar renders English labels", () => {
    cy.visit(FRONTEND_BASE);
    cy.wait("@getDevices");
    cy.get("nav").contains("Presets").should("exist");
    cy.get("nav").contains("Zones").should("exist");
    cy.get("nav").contains("Settings").should("exist");
  });
});

// ─── German language switch ───────────────────────────────────────────────────

describe("Wizard i18n — German (language switch)", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.visit(FRONTEND_BASE);
    cy.wait("@getDevices");
    // Switch language to German via LanguageSelector
    cy.get("[aria-label='Select language']").click();
    cy.get("[role='option']").contains("DE").click();
  });

  afterEach(() => {
    // Reset language to English
    cy.get("[aria-label='Select language']").click();
    cy.get("[role='option']").contains("EN").click();
  });

  it("navigation bar switches to German", () => {
    cy.get("nav").contains("Presets").should("not.exist");
    cy.get("nav").contains("Voreinstellungen").should("exist");
  });

  it("Step 2 title switches to German after language change", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=2&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.contains("USB-Stick vorbereiten").should("exist");
    cy.contains("Prepare USB drive").should("not.exist");
  });

  it("Step 6 domain labels are in German", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=6&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.contains("Hosts-Datei ändern").should("exist");
    cy.contains("Erforderlich").should("exist");
  });

  it("Step 8 completion title is in German", () => {
    cy.visit(`${FRONTEND_BASE}/setup/wizard?step=8&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79&deviceName=Wohnzimmer`);
    cy.contains("Setup abgeschlossen").should("exist");
  });
});

// ─── Language Selector UI ─────────────────────────────────────────────────────

describe("LanguageSelector — flag-icons rendering", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.visit(FRONTEND_BASE);
    cy.wait("@getDevices");
  });

  it("shows language selector button", () => {
    cy.get("[aria-label='Select language']").should("exist").and("be.visible");
  });

  it("flag is rendered as CSS class element (fi fi-*), not emoji text", () => {
    cy.get("[aria-label='Select language']")
      .find(".fi")
      .should("exist")
      .and("have.class", "fi");
  });

  it("opens dropdown with 4 language options", () => {
    cy.get("[aria-label='Select language']").click();
    cy.get("[role='listbox'] [role='option']").should("have.length", 4);
  });

  it("dropdown shows English, German, French, Italian options", () => {
    cy.get("[aria-label='Select language']").click();
    cy.get("[role='option']").contains("English").should("exist");
    cy.get("[role='option']").contains("Deutsch").should("exist");
    cy.get("[role='option']").contains("Français").should("exist");
    cy.get("[role='option']").contains("Italiano").should("exist");
  });

  it("each option has a flag-icons CSS element", () => {
    cy.get("[aria-label='Select language']").click();
    cy.get("[role='option'] .fi").should("have.length.at.least", 4);
  });

  it("selecting German updates the active language to DE", () => {
    cy.get("[aria-label='Select language']").click();
    cy.get("[role='option']").contains("Deutsch").click();
    cy.get("[aria-label='Select language']").contains("DE").should("exist");
    // Reset
    cy.get("[aria-label='Select language']").click();
    cy.get("[role='option']").contains("English").click();
  });
});

// ─── Stale device indicator (MultiRoom) ──────────────────────────────────────

describe("MultiRoom — stale device indicator", () => {
  it("shows warning triangle for devices not seen in 24+ hours", () => {
    const staleDate = new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString();
    cy.intercept("GET", "/api/devices", {
      statusCode: 200,
      body: {
        devices: [
          { ...MOCK_DEVICE, last_seen: staleDate },
        ],
      },
    }).as("getDevicesStale");

    cy.visit(FRONTEND_BASE);
    cy.wait("@getDevicesStale");
    cy.contains("Zones").click();

    // Stale indicator present
    cy.get(".device-stale, [data-testid='stale-indicator'], .stale").should("exist");
  });

  it("does not show stale indicator for recently seen devices", () => {
    const freshDate = new Date(Date.now() - 60 * 1000).toISOString(); // 1 minute ago
    cy.intercept("GET", "/api/devices", {
      statusCode: 200,
      body: {
        devices: [
          { ...MOCK_DEVICE, last_seen: freshDate },
        ],
      },
    }).as("getDevicesFresh");

    cy.visit(FRONTEND_BASE);
    cy.wait("@getDevicesFresh");
    cy.contains("Zones").click();

    cy.get(".device-stale, .stale").should("not.exist");
  });
});
