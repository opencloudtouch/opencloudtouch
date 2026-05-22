/**
 * E2E Tests: Preset Search Modal & Wizard Emoji Rendering
 *
 * 1. Preset Search Modal — verifies it renders centered (not left-aligned)
 * 2. Wizard pages — verifies emoji/symbols render correctly (not as mojibake)
 */

const FRONTEND_BASE = "http://localhost:4173";

const MOCK_DEVICE = {
  device_id: "DEVICE_WOHNZIMMER",
  name: "Wohnzimmer",
  model: "SoundTouch 300",
  ip: "192.168.1.79",
  mac: "A4:15:88:AA:BB:CC",
  type: "soundtouch",
};

function setupBasicMocks() {
  cy.intercept("GET", "/api/devices", {
    statusCode: 200,
    body: { devices: [MOCK_DEVICE] },
  }).as("getDevices");

  cy.intercept("GET", "/api/devices/*/now-playing", {
    statusCode: 200,
    body: { source: "STANDBY", status: null },
  });

  cy.intercept("GET", "/api/devices/*/volume", {
    statusCode: 200,
    body: { actual_volume: 30, muted: false },
  });

  cy.intercept("GET", "/api/presets/*", {
    statusCode: 200,
    body: {
      presets: [
        { preset_number: 1, station_name: "Radio 1", station_url: "http://r1.com", source_account: null },
        { preset_number: 2, station_name: null, station_url: null, source_account: null },
        { preset_number: 3, station_name: null, station_url: null, source_account: null },
      ],
    },
  }).as("getPresets");

  cy.intercept("GET", "/api/radio/search*", {
    statusCode: 200,
    body: { stations: [] },
  }).as("radioSearch");
}

function setupWizardMocks() {
  setupBasicMocks();
  cy.intercept("POST", "/api/setup/wizard/check-ports", {
    statusCode: 200,
    body: { success: true, has_ssh: true, has_telnet: false, message: "SSH available" },
  }).as("checkPorts");
  cy.intercept("GET", "/api/setup/server-info", {
    statusCode: 200,
    body: { server_url: "http://192.168.1.100:7777" },
  }).as("serverInfo");
  cy.intercept("POST", "/api/setup/wizard/detect-strategy", {
    statusCode: 200,
    body: { proxy_available: false, strategy: "bmx_and_hosts", message: "No proxy" },
  }).as("detectStrategy");
}

// ─── Preset Search Modal ──────────────────────────────────────────────────────

describe("Preset Search Modal — layout", () => {
  beforeEach(() => {
    setupBasicMocks();
    cy.visit(FRONTEND_BASE);
    cy.wait("@getDevices");
    cy.wait("@getPresets");
  });

  it("modal is rendered as div[role=dialog], not as dialog element", () => {
    // Click an empty preset slot (preset 2 or 3) to open search modal
    cy.get("[data-preset='2'], .preset-empty").first().click();
    cy.get("[role='dialog'].radio-search-modal").should("exist");
    // Must NOT be a native dialog element
    cy.get("dialog.radio-search-modal").should("not.exist");
  });

  it("modal overlay has correct flexbox centering styles", () => {
    cy.get("[data-preset='2'], .preset-empty").first().click();
    cy.get(".radio-search-overlay").should("exist").then(($overlay) => {
      const styles = window.getComputedStyle($overlay[0]);
      expect(styles.display).to.equal("flex");
      expect(styles.alignItems).to.equal("center");
      expect(styles.justifyContent).to.equal("center");
    });
  });

  it("modal is visually centered (left edge > 0)", () => {
    cy.get("[data-preset='2'], .preset-empty").first().click();
    cy.get(".radio-search-modal").should("exist").then(($modal) => {
      const rect = $modal[0].getBoundingClientRect();
      // Must not be at the very left edge
      expect(rect.left).to.be.greaterThan(10);
      // Must be roughly centered: left > 10% of viewport width
      expect(rect.left).to.be.greaterThan(window.innerWidth * 0.1);
    });
  });

  it("modal closes on overlay click", () => {
    cy.get("[data-preset='2'], .preset-empty").first().click();
    cy.get(".radio-search-modal").should("exist");
    cy.get(".radio-search-overlay").click("topLeft");
    cy.get(".radio-search-modal").should("not.exist");
  });

  it("modal closes on Escape key", () => {
    cy.get("[data-preset='2'], .preset-empty").first().click();
    cy.get(".radio-search-modal").should("exist");
    cy.get(".radio-search-overlay").type("{esc}");
    cy.get(".radio-search-modal").should("not.exist");
  });
});

// ─── Wizard Emoji Rendering ───────────────────────────────────────────────────

/**
 * These tests verify that emoji and Unicode symbols in wizard components render
 * correctly and NOT as mojibake (double-encoded UTF-8 displayed as Latin-1).
 *
 * Mojibake examples:
 *   🔌 → ðŸ"Œ   ⚠️ → âš ï¸   ✅ → âœ…   ❌ → â
 */

const MOJIBAKE_PATTERNS = [
  "ðŸ",   // emoji mojibake prefix
  "âœ",   // ✅ mojibake
  "âš",   // ⚠️ / ⚙️ mojibake
  "âž",   // ➕ mojibake
  "â†",   // → / ← mojibake
  "â³",   // ⏳ mojibake
  "ðŸ\u201DŒ", // 🔌 exact
  "âš ï¸", // ⚠️ exact
];

function assertNoMojibake() {
  cy.get("body").invoke("text").then((text) => {
    for (const pattern of MOJIBAKE_PATTERNS) {
      expect(text, `Page should not contain mojibake: "${pattern}"`).not.to.include(pattern);
    }
  });
}

describe("Wizard Step 2 — USB Preparation (emoji rendering)", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.visit(`${FRONTEND_BASE}/setup-wizard?step=2&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.wait("@getDevices");
  });

  it("does not render any mojibake characters", () => {
    assertNoMojibake();
  });

  it("USB plug icon renders correctly (🔌 not ðŸ\"Œ)", () => {
    cy.get(".usb-icon").invoke("text").then((text) => {
      expect(text).to.include("🔌");
      expect(text).not.to.include("ðŸ");
    });
  });

  it("device info shows USB-A for SoundTouch 300", () => {
    // Model "SoundTouch 300" includes "300" → USB-A
    cy.get(".usb-device-details").should("contain.text", "USB-A");
  });
});

describe("Wizard Step 3 — Power Cycle (emoji rendering)", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.visit(`${FRONTEND_BASE}/setup-wizard?step=3&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.wait("@getDevices");
  });

  it("does not render any mojibake characters", () => {
    assertNoMojibake();
  });
});

describe("Wizard Step 4 — Backup (emoji rendering)", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.intercept("POST", "/api/setup/wizard/backup", {
      statusCode: 200,
      body: { success: true, message: "Backup OK", volumes: [], total_size_mb: 0, total_duration_seconds: 0, backup_path: "/usb/backup" },
    }).as("backup");
    cy.visit(`${FRONTEND_BASE}/setup-wizard?step=4&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.wait("@getDevices");
  });

  it("does not render any mojibake characters", () => {
    assertNoMojibake();
  });
});

describe("Wizard Step 5 — Config Modification (emoji rendering)", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.visit(`${FRONTEND_BASE}/setup-wizard?step=5&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.wait("@getDevices");
  });

  it("does not render any mojibake characters", () => {
    assertNoMojibake();
  });

  it("warning icon renders correctly (⚠️ not âš ï¸)", () => {
    // Trigger validation error to show warning
    cy.get("#oct-url").should("exist").clear();
    cy.get(".config-modify-btn, button[disabled]").should("exist");
    assertNoMojibake();
  });

  it("gear icon on apply button renders correctly (⚙️ not âš™ï¸)", () => {
    cy.get(".config-modify-btn").invoke("text").then((text) => {
      expect(text).not.to.include("âš");
    });
  });
});

describe("Wizard Step 6 — Hosts Modification (emoji rendering)", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.visit(`${FRONTEND_BASE}/setup-wizard?step=6&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.wait("@getDevices");
  });

  it("does not render any mojibake characters", () => {
    assertNoMojibake();
  });
});

describe("Wizard Step 7 — Verification (emoji rendering)", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.intercept("POST", "/api/setup/wizard/finalize", {
      statusCode: 200,
      body: { success: true, uuid: "test-uuid-1234", had_uuid: false, uuid_was_collision: false, sources_written: true, sources_backup_path: "/tmp/backup", system_config_written: true, message: "Device finalized" },
    }).as("finalizeDevice");
    cy.intercept("POST", "/api/setup/wizard/reboot-device", {
      statusCode: 200,
      body: { success: true, message: "Reboot initiated" },
    }).as("rebootDevice");
    cy.intercept("POST", "/api/setup/wizard/verify-setup", {
      statusCode: 200,
      body: { success: true, checks: [{ name: "uuid", passed: true, message: "UUID set", details: {} }], passed_count: 1, failed_count: 0, message: "All checks passed" },
    }).as("verifySetup");
    cy.intercept("POST", "/api/setup/wizard/verify-redirect", {
      statusCode: 200,
      body: { success: true, resolved_ip: "192.168.1.100", expected_ip: "192.168.1.100", matches_expected: true, message: "OK" },
    }).as("verifyRedirect");
    cy.visit(`${FRONTEND_BASE}/setup-wizard?step=7&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.wait("@getDevices");
    // Click Finalize to transition setupPhase from idle to done_finalize
    cy.contains("button", /finalize|abschließen/i).click();
    cy.wait("@finalizeDevice");
  });

  it("does not render any mojibake characters", () => {
    assertNoMojibake();
  });

  it("reboot icon renders correctly (🔄 not mojibake)", () => {
    // After finalize, reboot section becomes visible with 🔄 icon
    cy.get(".reboot-section", { timeout: 5000 }).should("exist");
    cy.get(".reboot-icon").invoke("text").then((text) => {
      expect(text).not.to.include("ðŸ");
    });
  });

  it("success icon renders correctly after finalize (✅ not âœ…)", () => {
    // Finalize result shows ✅ on success
    cy.get(".finalize-result .success-icon", { timeout: 5000 }).invoke("text").then((text) => {
      expect(text).to.include("✅");
      expect(text).not.to.include("âœ");
    });
  });
});

describe("Wizard Step 8 — Completion (emoji rendering)", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.visit(`${FRONTEND_BASE}/setup-wizard?step=8&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79&deviceName=Wohnzimmer`);
    cy.wait("@getDevices");
  });

  it("does not render any mojibake characters", () => {
    assertNoMojibake();
  });

  it("party popper icon renders correctly (🎉 not ðŸŽ‰)", () => {
    cy.get(".completion-icon").invoke("text").then((text) => {
      expect(text).to.include("🎉");
      expect(text).not.to.include("ðŸŽ");
    });
  });

  it("checkmarks in summary list render correctly (✅ not âœ…)", () => {
    cy.get(".summary-icon").first().invoke("text").then((text) => {
      expect(text).to.include("✅");
      expect(text).not.to.include("âœ");
    });
  });

  it("done button renders with correct text", () => {
    cy.get(".completion-btn-done").invoke("text").then((text) => {
      expect(text.trim()).to.match(/Done|Fertig/);
    });
  });
});

describe("WizardStep base — warning icon rendering", () => {
  beforeEach(() => {
    setupWizardMocks();
    cy.visit(`${FRONTEND_BASE}/setup-wizard?step=2&deviceId=DEVICE_WOHNZIMMER&deviceIp=192.168.1.79`);
    cy.wait("@getDevices");
  });

  it("warning icon in WizardStep header renders correctly (⚠️ not âš ï¸)", () => {
    // Step 2 has a warning prop set → WizardStep renders the warning section
    cy.get(".wizard-warning, .step-warning").should("exist").invoke("text").then((text) => {
      expect(text).not.to.include("âš");
      expect(text).not.to.include("ï¸");
    });
  });

  it("back arrow in navigation renders correctly (← not â†)", () => {
    cy.get(".wizard-nav-prev, .btn-back, [aria-label*='Back'], [aria-label*='back']")
      .first()
      .invoke("text")
      .then((text) => {
        expect(text).not.to.include("â†");
      });
  });

  it("forward arrow in navigation renders correctly (→ not â†')", () => {
    cy.get(".wizard-nav-next, .btn-next, button").contains(/Next|Weiter/).invoke("text").then((text) => {
      expect(text).not.to.include("â†");
    });
  });
});
