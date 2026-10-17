/**
 * E2E Test: Setup Wizard — optional NTP server step (Issue #469)
 *
 * Covers the behaviour of the step itself (patch, failure, skip) with the
 * backend mocked. The ntp_server -> verify-setup wiring is covered by unit tests;
 * the emoji rendering of the step lives in wizard-ui-rendering.cy.ts.
 */

const FRONTEND_BASE = "http://localhost:4173";
const DEVICE_IP = "192.168.1.79";
const NTP_STEP_URL = `${FRONTEND_BASE}/setup-wizard?step=7&deviceId=DEVICE_WOHNZIMMER&deviceIp=${DEVICE_IP}`;

const MOCK_DEVICE = {
  device_id: "DEVICE_WOHNZIMMER",
  name: "Wohnzimmer",
  model: "SoundTouch 10",
  ip: DEVICE_IP,
  mac: "A4:15:88:AA:BB:CC",
  type: "soundtouch",
};

function visitNtpStep() {
  cy.intercept("GET", "/api/devices", {
    statusCode: 200,
    body: { devices: [MOCK_DEVICE] },
  }).as("getDevices");

  cy.visit(NTP_STEP_URL, {
    onBeforeLoad(win) {
      win.localStorage.setItem("oct-lang", "en");
    },
  });
  cy.wait("@getDevices");
}

describe("Setup Wizard — NTP step (#469)", () => {
  it("offers pool.ntp.org by default and keeps Next disabled until patched", () => {
    visitNtpStep();

    cy.get("#ntp-server").should("have.value", "pool.ntp.org");
    cy.contains("button", /^next/i).should("be.disabled");
    cy.contains("button", /skip/i).should("exist");
  });

  it("patches the device with the entered server and then enables Next", () => {
    cy.intercept("POST", "/api/setup/wizard/patch-ntp", {
      statusCode: 200,
      body: {
        success: true,
        message: "NTP server patched",
        synced: true,
        backup_path: "/mnt/nv/ntpservers_backup",
        diff: "+ ntp.example.local",
      },
    }).as("patchNtp");
    visitNtpStep();

    cy.get("#ntp-server").clear().type("  ntp.example.local  ");
    cy.get(".ntp-patch-btn").click();

    cy.wait("@patchNtp")
      .its("request.body")
      .should("deep.equal", { device_ip: DEVICE_IP, ntp_server: "ntp.example.local" });

    cy.get(".ntp-success").should("be.visible");
    cy.get("#ntp-server").should("not.exist");
    // Skipping after a successful patch would discard it, so Skip is gone.
    cy.contains("button", /skip/i).should("not.exist");
    cy.contains("button", /^next/i).should("not.be.disabled").click();

    // Landed on Verification (Step 8)
    cy.contains("button", /finalize/i, { timeout: 5000 }).should("exist");
  });

  it("shows the backend error, keeps Next disabled and still allows Skip", () => {
    cy.intercept("POST", "/api/setup/wizard/patch-ntp", {
      statusCode: 200,
      body: {
        success: false,
        message: "Cannot back up /etc/ntpservers.txt",
        synced: false,
        backup_path: "",
        diff: "",
      },
    }).as("patchNtp");
    visitNtpStep();

    cy.get(".ntp-patch-btn").click();
    cy.wait("@patchNtp");

    cy.get(".ntp-error").should("contain.text", "Cannot back up /etc/ntpservers.txt");
    cy.contains("button", /^next/i).should("be.disabled");
    cy.contains("button", /skip/i).should("exist");
  });

  it("skips the step without calling the backend", () => {
    cy.intercept("POST", "/api/setup/wizard/patch-ntp", cy.spy().as("patchNtpSpy"));
    visitNtpStep();

    cy.contains("button", /skip/i).click();

    cy.contains("button", /finalize/i, { timeout: 5000 }).should("exist");
    cy.get("@patchNtpSpy").should("not.have.been.called");
  });
});

describe("Setup Wizard API — patch-ntp input validation", () => {
  const API = "http://localhost:4173/api/setup";

  it("rejects an NTP server containing shell metacharacters (422)", () => {
    cy.request({
      method: "POST",
      url: `${API}/wizard/patch-ntp`,
      body: { device_ip: DEVICE_IP, ntp_server: "ntp.example.local; reboot" },
      failOnStatusCode: false,
    }).then((resp) => {
      expect(resp.status).to.equal(422);
    });
  });
});
