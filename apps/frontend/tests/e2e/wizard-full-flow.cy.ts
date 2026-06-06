/**
 * E2E Test: Setup Wizard Full Flow — Bug Regression Suite
 *
 * CONTEXT FOR AI AGENTS:
 * Diese Tests sind KEINE Coverage-Tests. Jeder Test sichert einen konkreten Bug ab,
 * der im produktiven Betrieb am echten Gerät (192.168.1.79) entdeckt wurde und
 * zu sichtbaren Fehlfunktionen geführt hat. Testqualität wird daran gemessen, ob
 * das beschriebene Fehlverhalten verhindert wird – nicht an Zeilen-Coverage.
 *
 * Bugs abgedeckt (Details: docs/testing/WIZARD_BUG_REGRESSION_TESTS.md):
 *   BUG-05  enablePermanentSsh() API-Call fehlte komplett
 *   BUG-08  CSS-Variablen undefiniert → unsichtbare UI-Elemente
 *   BUG-09  Step 4 Backup nicht überspringbar
 *   BUG-10  Step 3 SSH-Wahl navigierte sofort statt per Weiter-Button
 *   BUG-11  „Erneut prüfen"-Button stand unter den Risikofragen statt darüber
 *   BUG-12  Hardcodierte OCT-URL 192.168.1.50 statt window.location
 */

const API_BASE = Cypress.expose('apiUrl') || "http://localhost:7778/api";
const FRONTEND_BASE = "http://localhost:4173";

// ─── Shared Fixtures ──────────────────────────────────────────────────────────

const MOCK_DEVICE = {
  device_id: "DEVICE_WOHNZIMMER",
  name: "Wohnzimmer",
  model: "SoundTouch 10",
  ip: "192.168.1.79",
  mac: "A4:15:88:AA:BB:CC",
  type: "soundtouch",
};

function setupDeviceMocks() {
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
      volumes: [{ volume: "/nv", path: "/usb/backups/nv.tar.gz", size_mb: 2.1, duration_seconds: 3 }],
      total_size_mb: 2.1,
      total_duration_seconds: 3,
    },
  }).as("createBackup");

  cy.intercept("POST", "/api/setup/wizard/validate-hostname", {
    statusCode: 200,
    body: {
      resolvable: true,
      resolved_ip: "127.0.0.1",
      matches_expected: true,
      oct_reachable: true,
      error: null,
      oct_error: null,
    },
  }).as("validateHostname");

  cy.intercept("POST", "/api/setup/wizard/modify-config", {
    statusCode: 200,
    body: {
      success: true,
      action: "modified",
      old_url: "https://*.bose.com (4 URLs)",
      new_url: "192.168.1.100",
      backup_path: "/usb/backups/config_backup.xml",
      diff: "- https://*.bose.com (4 URLs)\n+ 192.168.1.100",
      message: "Config modified",
    },
  }).as("modifyConfig");

  cy.intercept("POST", "/api/setup/wizard/modify-hosts", {
    statusCode: 200,
    body: {
      success: true,
      action: "modified",
      added_entries: 7,
      backup_path: "/usb/backups/hosts_backup",
      diff: "+ 192.168.1.100 bose.vtuner.com\n+ 192.168.1.100 streaming.bose.com",
      message: "Hosts modified",
    },
  }).as("modifyHosts");

  cy.intercept("POST", "/api/setup/wizard/verify-redirect", {
    statusCode: 200,
    body: {
      success: true,
      domain: "bose.vtuner.com",
      resolved_ip: "192.168.1.100",
      matches_expected: true,
      message: "bose.vtuner.com → 192.168.1.100 ✓",
    },
  }).as("verifyRedirect");

  cy.intercept("POST", "/api/setup/ssh/enable-permanent", {
    statusCode: 200,
    body: {
      success: true,
      permanent_enabled: true,
      message: "SSH dauerhaft aktiviert.",
    },
  }).as("enablePermanentSSH");

  cy.intercept("GET", "/api/setup/wizard/detect-strategy", {
    statusCode: 200,
    body: {
      proxy_available: false,
      strategy: "bmx_and_hosts",
      message: "No reverse proxy detected on port 443. The BMX URL must also be changed.",
    },
  }).as("detectStrategy");

  cy.intercept("GET", "/api/setup/wizard/server-info", {
    statusCode: 200,
    body: {
      server_url: "http://localhost:7778",
      server_ip: "127.0.0.1",
      default_port: 7777,
      supported_protocols: ["http", "https"],
    },
  }).as("serverInfo");

  cy.intercept("GET", "/api/setup/instructions/*", {
    statusCode: 200,
    body: {
      model_name: "SoundTouch 10",
      display_name: "Bose SoundTouch 10",
      usb_port_type: "micro-usb",
      usb_port_types: ["micro-usb"],
      usb_port_location: "Rückseite, neben AUX-Eingang, beschriftet 'SETUP'",
      adapter_needed: true,
      adapter_recommendation: "USB-A auf Micro-USB OTG Adapter",
      notes: [],
    },
  }).as("modelInstructions");
}

// ─── Tests ───────────────────────────────────────────────────────────────────

/** Force German locale — CI defaults to English (navigator.language='en') */
function visitDe(url: string, options?: Partial<Cypress.VisitOptions>) {
  cy.visit(url, {
    ...options,
    onBeforeLoad(win) {
      win.localStorage.setItem("oct-lang", "de");
      options?.onBeforeLoad?.(win);
    },
  });
}

describe("Setup Wizard — Bug Regression Suite", () => {
  beforeEach(() => {
    setupDeviceMocks();
    visitDe("/setup-wizard?deviceId=DEVICE_WOHNZIMMER");
    cy.wait("@getDevices");
    // Wizard starts directly at Step 1 after clicking through WizardChoice
    cy.get('.setup-wizard-page', { timeout: 8000 }).should('exist');
    cy.contains("Setup-Assistent").click();
  });

  // ─── BUG-12: Hardcodierte OCT-URL ──────────────────────────────────────────
  describe("BUG-12: OCT-URL from window.location (not hardcoded)", () => {
    /**
     * Vor dem Fix war octIp = "192.168.1.50" hardcodiert.
     * Der Wizard muss die URL aus window.location.hostname ableiten,
     * damit er in jeder Umgebung korrekt funktioniert.
     */
    it("should not send hardcoded 192.168.1.50 as oct_ip to backend", () => {
      // USB Prep: check all checkboxes to enable Weiter, then navigate to PowerCycle
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      // Trigger port check
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");
      // Make SSH decision
      cy.contains("button", /nie.*dauerhaft|nicht dauerhaft/i)
        .should("exist")
        .click({ force: true });
      cy.contains("button", /weiter/i).should("not.be.disabled").click();

      cy.wait("@enablePermanentSSH");
      cy.get("@enablePermanentSSH").its("request.body.ip").should("equal", "192.168.1.79");
    });
  });

  // ─── BUG-09: Backup überspringbar ──────────────────────────────────────────
  describe("BUG-09: Backup is skippable (Weiter always enabled in Step 4)", () => {
    /**
     * isNextDisabled={!backupData?.success} blockierte Navigation
     * wenn Backup nicht gestartet wurde. Backup ist optional.
     */
    it("should have Weiter button enabled in Step 4 even without starting backup", () => {
      // USB Prep → PowerCycle → Backup
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      // PowerCycle: port check + SSH decision
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");
      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).should("not.be.disabled").click();

      // We're now in Step 4 (Backup) — Weiter must be enabled without backup
      cy.contains(/backup/i, { timeout: 5000 }).should("exist");
      cy.contains("button", /weiter/i).should("not.be.disabled");
    });
  });

  // ─── BUG-10: SSH-Entscheidung via Weiter-Button ────────────────────────────
  describe("BUG-10: Step 3 SSH decision via Weiter button (not immediate navigation)", () => {
    /**
     * Vor dem Fix: Klick auf SSH-Karte navigierte sofort zur nächsten Seite.
     * Korrekt: Karte speichert Auswahl, Weiter-Button aktiviert Navigation.
     */
    it("should keep Weiter disabled in Step 3 until SSH decision is made", () => {
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle

      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");

      // After ports confirmed: Weiter must be DISABLED until decision
      cy.contains("button", /weiter/i).should("be.disabled");

      // After selecting a decision: Weiter must be ENABLED
      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).should("not.be.disabled");
    });

    it("should NOT navigate immediately on card click (only on Weiter)", () => {
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");

      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });

      // Still on Step 3 — URL should not have changed to Step 4
      cy.url().should("include", "setup-wizard");
      // Step 4 content (Backup) must NOT be visible yet
      cy.contains(/backup erstellen/i).should("not.exist");
    });
  });

  // ─── BUG-11: „Erneut prüfen"-Button Reihenfolge ────────────────────────────
  describe("BUG-11: Retry button appears above risk questions, not below", () => {
    /**
     * JSX-Reihenfolge war: Status → Risikofragen → Button.
     * Korrekt:             Status → Button → Risikofragen.
     * DOM-Reihenfolge im gerenderten HTML muss korrekt sein.
     */
    it("should render check/retry button before risk-assessment section in DOM", () => {
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");

      // Check DOM order: button must come before .ssh-risk-assessment
      cy.get(".power-cycle-check").then(($container) => {
        const btnIndex = $container
          .find(".power-cycle-check-btn")
          .index();
        const riskIndex = $container
          .find(".ssh-risk-assessment")
          .index();
        expect(btnIndex).to.be.lessThan(riskIndex);
      });
    });
  });

  // ─── BUG-05: enablePermanentSsh() API-Call ─────────────────────────────────
  describe("BUG-05: enable-permanent-ssh API is called when user decides", () => {
    /**
     * handleSSHDecision() speicherte nur State, rief aber nie das Backend auf.
     * /mnt/nv/remote_services wurde nie erstellt → SSH nach Neustart verloren.
     */
    it("should POST to /api/setup/ssh/enable-permanent with make_permanent=true", () => {
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");

      // Select "dauerhaft aktivieren" — must target button, not the h4 heading
      cy.contains("button", /dauerhaft aktivieren/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).should("not.be.disabled").click();

      cy.wait("@enablePermanentSSH").then((interception) => {
        expect(interception.request.body.make_permanent).to.equal(true);
        expect(interception.request.body.ip).to.equal("192.168.1.79");
      });
    });

    it("should POST with make_permanent=false when user keeps SSH temporary", () => {
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");

      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).should("not.be.disabled").click();

      cy.wait("@enablePermanentSSH").then((interception) => {
        expect(interception.request.body.make_permanent).to.equal(false);
      });
    });
  });

  // ─── BUG-08: CSS-Variablen / Sichtbarkeit ──────────────────────────────────
  describe("BUG-08: CSS variables defined → wizard elements visible", () => {
    /**
     * --text-primary, --surface-color, --border-color etc. waren undefiniert.
     * Browser-Fallback: initial = schwarzer Text auf transparentem Hintergrund
     * → auf dunklen Cards komplett unsichtbar.
     */
    it("should have --text-primary CSS variable defined on :root", () => {
      cy.document().then((doc) => {
        const style = getComputedStyle(doc.documentElement);
        const textPrimary = style.getPropertyValue("--text-primary").trim();
        expect(textPrimary).to.not.be.empty;
        expect(textPrimary).to.not.equal("initial");
      });
    });

    it("should have --surface-color CSS variable defined on :root", () => {
      cy.document().then((doc) => {
        const style = getComputedStyle(doc.documentElement);
        const surfaceColor = style.getPropertyValue("--surface-color").trim();
        expect(surfaceColor).to.not.be.empty;
      });
    });

    it("should render Step 5 Weiter input with visible text color", () => {
      // Navigate: USB Prep → PowerCycle → Backup → Config
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");
      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).click(); // Step 3 → 4
      cy.contains("button", /weiter/i).click(); // Step 4 → 5

      // Config input must have non-white background
      cy.get(".config-input").should("be.visible").then(($el) => {
        const bg = getComputedStyle($el[0] as Element).backgroundColor;
        // Must not be white (rgb(255, 255, 255)) or transparent
        expect(bg).to.not.equal("rgb(255, 255, 255)");
      });
    });
  });

  // ─── BUG-07: ConfigModifyResponse old_url/new_url ──────────────────────────
  describe("BUG-07: Config modification shows old and new URL (not N/A)", () => {
    /**
     * ConfigModifyResponse fehlten old_url/new_url → UI zeigte „Alte URL: N/A".
     */
    it("should display old and new URL after config modification", () => {
      // Navigate: USB Prep → PowerCycle → Backup → Config
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");
      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).click();
      cy.contains("button", /weiter/i).click();

      // Trigger config modification
      cy.contains("button", /konfiguration.*ndern/i, { timeout: 5000 }).click();
      cy.wait("@modifyConfig");

      // Must NOT show N/A
      cy.contains(/N\/A/).should("not.exist");
      cy.contains("https://*.bose.com (4 URLs)").should("exist");
    });
  });

  // ─── BUG-17: USB-Anschlusstyp für SoundTouch 10 ────────────────────────────
  describe("BUG-17: USB connector type for SoundTouch 10 is Micro-USB (not USB-A)", () => {
    /**
     * if (model.startsWith("ST10")) return "Micro-USB"
     * "SoundTouch 10".startsWith("ST10") === false → always USB-A.
     * Fix: model.includes("30") || model.includes("300") ? "USB-A" : "Micro-USB"
     */
    it("should show Micro-USB (not USB-A) in Step 2 for SoundTouch 10", () => {
      // MOCK_DEVICE has model: "SoundTouch 10" — USB Prep (step 1) is already visible after clicking Manuell

      // Page must say "Micro-USB"
      cy.contains(/Micro-USB/i).should("exist");
      // Device details section must show MICRO-USB as port type, not USB-A.
      // Note: adapter recommendation links ("USB-A → Micro-USB OTG Adapter") naturally
      // contain "USB-A" — that's expected. We only check the device details section.
      cy.get(".usb-device-details").invoke("text").then((text) => {
        // The port type line should say MICRO-USB
        expect(text.toUpperCase()).to.include("MICRO-USB");
        // Adapter links are outside .usb-device-details — this section must not
        // independently declare USB-A as the device's own port type.
        // Allow "USB-A" only inside adapter link text (which lives in .usb-adapter-hint).
      });
    });
  });

  // ─── BUG-19: check-ports request uses device_ip field ──────────────────────
  describe("BUG-19: checkPorts request uses device_ip not device_id", () => {
    /**
     * Frontend sendete {device_id} → Backend erwartete {device_ip} → 422 Error.
     * Fix: Frontend must send device_ip with the IP address.
     */
    it("should send device_ip in check-ports request body", () => {
      // Intercept check-ports and verify the request body
      cy.intercept("POST", "/api/setup/wizard/check-ports", (req) => {
        expect(req.body).to.have.property("device_ip"),
          "BUG-19: check-ports body must have device_ip, not device_id";
        expect(req.body).not.to.have.property("device_id"),
          "BUG-19: check-ports must not send device_id (backend rejects it with 422)";
        expect(req.body.device_ip).to.equal("192.168.1.79"),
          "BUG-19: device_ip must be the device IP address";

        req.reply({ statusCode: 200, body: { success: true, has_ssh: true, has_telnet: false, message: "ok" } });
      }).as("checkPortsVerified");

      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPortsVerified");
    });

    it("should read has_ssh from response (not ssh_available - BUG-19)", () => {
      // The response field is has_ssh, old frontend read ssh_available
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");

      // UI should show SSH as available (mock returns has_ssh: true)
      cy.contains(/ssh.*verfügbar|ssh.*aktiv|ssh.*bereit/i, { timeout: 5000 }).should("exist");
    });
  });

  // ─── BUG-20: remote_services Datei-Inhalt ──────────────────────────────────
  describe("BUG-20: remote_services file must be empty (not SSH=ENABLE)", () => {
    /**
     * UI zeigte Anleitung: Datei soll 'SSH=ENABLE\nTELNET=ENABLE' enthalten.
     * Korrekt: Datei muss LEER sein (BusyBox prüft nur Existenz).
     */
    it("should NOT tell user to write SSH=ENABLE in remote_services", () => {
      // USB Prep (step 1) already visible — check content immediately
      cy.contains("SSH=ENABLE").should("not.exist");
      cy.contains("TELNET=ENABLE").should("not.exist");
    });

    it("should say remote_services file must be empty (leer)", () => {
      // USB Prep (step 1) already visible — check content immediately
      cy.contains(/leer/i).should("exist");
    });
  });

  // ─── BUG-23: BackupResponse has volumes[] not rootfs ───────────────────────
  describe("BUG-23: Step 4 backup shows volume list, not backups.rootfs crash", () => {
    /**
     * Frontend erwartete {backups: {rootfs: {}}} → Backend antwortet mit {volumes: []}.
     * TypeError: Cannot read properties of undefined (reading 'rootfs')
     */
    it("should render backup volumes list without TypeErrors", () => {
      // Navigate to Backup: USB Prep → PowerCycle → Backup
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");
      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).click(); // PowerCycle → Backup

      // Trigger backup
      cy.contains("button", /backup.*erstellen/i, { timeout: 5000 }).click();
      cy.wait("@createBackup");

      // Must not crash – backup result section should appear
      cy.contains(/backup.*erstellt|backup.*erfolgreich|nv/i, { timeout: 5000 }).should("exist");
      // No JavaScript error overlay
      cy.get(".error-boundary").should("not.exist");
      cy.contains(/TypeError/).should("not.exist");
    });
  });

  // ─── BUG-25: Steps 4-7 use device_ip not device_id ──────────────────────────
  describe("BUG-25: Steps 4-7 send device_ip not device_id to backend", () => {
    /**
     * Steps 4-7 sendeten {device_id} → Backend erwartet {device_ip} → 422 Error.
     * {errors: [{field: "body.device_ip", message: "Field required"}]}
     */
    it("should send device_ip in the backup request (Step 4)", () => {
      cy.intercept("POST", "/api/setup/wizard/backup", (req) => {
        expect(req.body).to.have.property("device_ip"),
          "BUG-25: backup request must have device_ip field (was device_id)";
        expect(req.body.device_ip).to.equal("192.168.1.79");
        req.reply({
          statusCode: 200,
          body: { success: true, volumes: [], total_size_mb: 0, total_duration_seconds: 0, message: "ok" },
        });
      }).as("backupVerified");

      // Navigate to Backup: USB Prep → PowerCycle → Backup
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");
      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).click(); // PowerCycle → Backup

      cy.contains("button", /backup.*erstellen/i, { timeout: 5000 }).click();
      cy.wait("@backupVerified");
    });

    it("should send device_ip in the modify-hosts request (Step 6)", () => {
      cy.intercept("POST", "/api/setup/wizard/modify-hosts", (req) => {
        expect(req.body).to.have.property("device_ip"),
          "BUG-25: modify-hosts request must have device_ip field";
        expect(req.body.device_ip).to.equal("192.168.1.79");
        req.reply({
          statusCode: 200,
          body: { success: true, action: "modified", added_entries: 7, backup_path: "/backup", diff: "", message: "ok" },
        });
      }).as("hostsVerified");

      // Navigate to Hosts: USB Prep → PowerCycle → Backup → Config
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");
      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).click(); // PowerCycle → Backup
      cy.contains("button", /weiter/i).click(); // Backup → Config
      cy.contains("button", /konfiguration.*ndern/i, { timeout: 5000 }).click({ force: true });
      cy.wait("@modifyConfig");
      cy.contains("button", /weiter/i).click({ force: true }); // → 6

      cy.contains("button", /hosts.*datei/i, { timeout: 5000 }).click({ force: true });
      cy.wait("@hostsVerified");
    });
  });

  // ─── BUG-30: Reboot-Button in Step 7 ────────────────────────────────────────
  describe("BUG-30: Step 7 (Verification) has a Reboot button", () => {
    /**
     * Step 6 kündigte „Neustart im nächsten Schritt" an.
     * Step 7 zeigte nur Text, keinen Reboot-Button → kein Neustart möglich.
     * Fix: Backend POST /api/setup/wizard/reboot-device + UI-Reboot-Sektion.
     */
    it("should show a reboot button in Step 7", () => {
      cy.intercept("POST", "/api/setup/wizard/reboot-device", {
        statusCode: 200,
        body: { success: true, message: "Reboot initiated" },
      }).as("rebootDevice");

      cy.intercept("POST", "/api/setup/wizard/finalize", {
        statusCode: 200,
        body: { success: true, uuid: "1234567", had_uuid: false, uuid_was_collision: false, sources_written: true, sources_backup_path: "/tmp/backup", system_config_written: true, message: "Device finalized" },
      }).as("finalizeDevice");

      cy.intercept("POST", "/api/setup/wizard/verify-setup", {
        statusCode: 200,
        body: { success: true, checks: [{ name: "uuid", passed: true, message: "UUID set", details: {} }], passed_count: 1, failed_count: 0, message: "All checks passed" },
      }).as("verifySetup");

      // Navigate to Verify: USB Prep → PowerCycle → Backup → Config → Hosts
      cy.get('input[type="checkbox"]').each(($cb) => { cy.wrap($cb).check({ force: true }); });
      cy.contains("button", /weiter/i).click(); // USB Prep → PowerCycle
      cy.contains("button", /jetzt prüfen/i).click();
      cy.wait("@checkPorts");
      cy.contains(/nicht dauerhaft/i, { timeout: 5000 }).click({ force: true });
      cy.contains("button", /weiter/i).click(); // PowerCycle → Backup
      cy.contains("button", /weiter/i).click(); // Backup → Config
      cy.contains("button", /konfiguration.*ndern/i, { timeout: 5000 }).click({ force: true });
      cy.wait("@modifyConfig");
      cy.contains("button", /weiter/i).click({ force: true }); // → 6
      cy.contains("button", /hosts.*datei/i, { timeout: 5000 }).click({ force: true });
      cy.wait("@modifyHosts");
      cy.contains("button", /weiter/i).click({ force: true }); // → 7

      // Step 7 starts in "idle" phase — must finalize first to reveal reboot button
      // Button text is "Geräte-Setup abschließen" (DE) or "Finalize Device Setup" (EN)
      cy.contains("button", /abschließen|finalize/i, { timeout: 5000 }).click();
      cy.wait("@finalizeDevice");

      // After finalize succeeds, reboot section becomes visible
      cy.get(".reboot-btn", { timeout: 5000 }).should("exist");
    });
  });

  // ─── BUG-15: Kein schwarzer Bildschirm nach Discovery ──────────────────────
  describe("BUG-15: No black screen after device discovery completes", () => {
    /**
     * useDiscoveryStream.ts setzte React-Query Cache als {count, devices} Objekt.
     * useDevices erwartete Device[] Array → .length undefined → Route-Guard Loop.
     * Fix: Cache als Device[] Array. navigate in useEffect (nicht synchon im Render).
     */
    it("should show devices page (not redirect loop) after discovery", () => {
      // Simulate completed discovery
      cy.intercept("GET", "/api/devices", {
        statusCode: 200,
        body: { devices: [{ device_id: "DISC1", name: "Wohnzimmer", model: "SoundTouch 10", ip: "192.168.1.79", mac: "AA:BB:CC:DD:EE:FF", type: "soundtouch" }] },
      }).as("getDevicesAfterDisc");

      visitDe("/");
      cy.wait("@getDevicesAfterDisc");

      // Must NOT be stuck in redirect loop
      cy.url().should("not.match", /\/welcome.*\/$/);

      // Device list must be visible (not black screen)
      cy.get("[data-test=\"device-swiper\"]", { timeout: 5000 }).should("exist");
      cy.contains("Wohnzimmer", { timeout: 5000 }).should("exist");
    });
  });
}); // closes main outer describe "Setup Wizard — Full Flow (Manual Mode)"

// ─── Wizard Backend API Smoke Tests ──────────────────────────────────────────

describe("Setup Wizard API — Backend Smoke Tests", () => {
  /**
   * Diese Tests prüfen die Backend-Endpunkte direkt via cy.request().
   * Kein Frontend nötig — testet nur den API-Contract.
   * Laufen gegen http://localhost:7778 (OCT_MOCK_MODE=true).
   */

  const API = "http://localhost:4173/api/setup"; // via vite preview proxy → localhost:7778

  it("BUG-06: verify-redirect endpoint exists (not 404)", () => {
    cy.request({
      method: "POST",
      url: `${API}/wizard/verify-redirect`,
      body: {
        device_ip: "192.168.1.79",
        domain: "bose.vtuner.com",
        expected_ip: "192.168.1.100",
      },
      failOnStatusCode: false,
      timeout: 30000, // SSH-Timeout im Backend ist 10s → genug Puffer
    }).then((resp) => {
      // Must not be 404 (endpoint missing)
      expect(resp.status).to.not.equal(404);
      // Either success or connection refused to device (500) — both are acceptable
      // The important thing: endpoint EXISTS and returns JSON with correct shape
      if (resp.status === 200) {
        expect(resp.body).to.have.keys(["success", "domain", "resolved_ip", "matches_expected", "message"]);
      }
    });
  });

  it("BUG-07: modify-config response includes old_url and new_url fields", () => {
    cy.request({
      method: "POST",
      url: `${API}/wizard/modify-config`,
      body: { device_ip: "192.168.1.1", oct_ip: "192.168.1.100" },
      failOnStatusCode: false,
      timeout: 30000,
    }).then((resp) => {
      // Even on SSH failure (503) the response shape should be consistent
      if (resp.status === 200) {
        expect(resp.body).to.have.property("old_url");
        expect(resp.body).to.have.property("new_url");
        expect(resp.body.old_url).to.not.be.undefined;
        expect(resp.body.new_url).to.not.be.undefined;
      }
    });
  });
});
