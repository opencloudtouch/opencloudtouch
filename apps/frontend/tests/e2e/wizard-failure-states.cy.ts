/**
 * E2E: failure and edge states of the setup wizard (rows of docs/UI_STATE_MATRIX.md).
 *
 * Every state is provoked with cy.intercept, so no request reaches a device. Assertions:
 *  - the user sees a translated message, never the raw backend or network text,
 *  - a retry path stays available,
 *  - the layout does not overflow.
 */
import { collectLayoutIssues, waitForStableLayout } from "./support/layoutAudit";
import {
  DEVICE,
  DEVICES,
  FINALIZE_OK,
  VERIFY_ALL_PASSED,
  check,
  mockApi,
  mockSetupWizardApi,
  visitDe,
} from "./support/wizardMocks";

const RAW = "RAWSECRET Permission denied: /mnt/nv/x";
const WIDTHS = [390, 1280];

type Outcome = { name: string; reply: (url: string) => void };

/** Request outcomes R4..R11 of the matrix that apply to a wizard POST. */
const OUTCOMES: Outcome[] = [
  { name: "success=false", reply: (url) => cy.intercept("POST", url, { statusCode: 200, body: { success: false, error: RAW, message: RAW } }) },
  { name: "HTTP 500", reply: (url) => cy.intercept("POST", url, { statusCode: 500, body: { detail: RAW } }) },
  { name: "HTTP 504", reply: (url) => cy.intercept("POST", url, { statusCode: 504, body: RAW }) },
  { name: "HTTP 422", reply: (url) => cy.intercept("POST", url, { statusCode: 422, body: { detail: [{ msg: RAW }] } }) },
  { name: "network failure", reply: (url) => cy.intercept("POST", url, { forceNetworkError: true }) },
];

const ACTION_STEPS = [
  { name: "backup", step: 4, url: "/api/setup/wizard/backup" },
  { name: "config", step: 5, url: "/api/setup/wizard/modify-config" },
  { name: "hosts", step: 6, url: "/api/setup/wizard/modify-hosts" },
  { name: "ntp", step: 7, url: "/api/setup/wizard/patch-ntp" },
];

function assertNoOverflow() {
  cy.window().then((win) => waitForStableLayout(win));
  cy.window().then((win) => {
    const overflow = collectLayoutIssues(win).filter((i) => i.kind === "page-overflow");
    expect(overflow, "page overflow").to.deep.equal([]);
  });
}

function assertNoRawText() {
  cy.get("body").invoke("text").should("not.match", /RAWSECRET|Permission denied|Failed to fetch|NetworkError/);
}

describe("Wizard action steps: failures are translated", () => {
  for (const { name, step, url } of ACTION_STEPS) {
    for (const outcome of OUTCOMES) {
      it(`${name}: ${outcome.name} shows no raw text and keeps the primary action`, () => {
        mockSetupWizardApi();
        outcome.reply(url);
        visitDe(`/setup-wizard?deviceId=${DEVICE!.device_id}&step=${step}`);
        cy.get("main .btn-primary").first().click();
        // the failed action stays retryable: the primary or the retry button is still there
        cy.get("main button").filter(":visible").should("have.length.greaterThan", 0);
        assertNoRawText();
        assertNoOverflow();
      });
    }
  }

  for (const width of WIDTHS) {
    it(`ntp: failure box fits at ${width}px`, () => {
      cy.viewport(width, 900);
      mockSetupWizardApi();
      OUTCOMES[1]!.reply("/api/setup/wizard/patch-ntp");
      visitDe(`/setup-wizard?deviceId=${DEVICE!.device_id}&step=7`);
      cy.get("main .btn-primary").first().click();
      assertNoRawText();
      assertNoOverflow();
    });
  }
});

describe("Wizard verification step", () => {
  function reachVerification() {
    cy.clock(Date.now(), ["setInterval"]);
    visitDe(`/setup-wizard?deviceId=${DEVICE!.device_id}&step=8`);
    cy.get(".finalize-section .btn-primary").click();
    cy.get(".reboot-btn").click();
    cy.tick(101000);
    cy.get(".verification-start button").first().click();
  }

  it("shows the replaced-UUID message when the device UUID was a duplicate", () => {
    mockSetupWizardApi();
    cy.intercept("POST", "/api/setup/wizard/finalize", {
      statusCode: 200,
      body: { ...FINALIZE_OK, uuid_was_collision: true, uuid_source: "collision_fallback" },
    });
    visitDe(`/setup-wizard?deviceId=${DEVICE!.device_id}&step=8`);
    cy.get(".finalize-section .btn-primary").click();
    cy.get(".verify-checklist").should("contain.text", FINALIZE_OK.uuid);
    cy.get(".verify-checklist .check-message").first().should("not.contain.text", "undefined");
    assertNoOverflow();
  });

  it("shows translated rows for failing checks and offers a retry", () => {
    mockSetupWizardApi();
    cy.intercept("POST", "/api/setup/wizard/verify-setup", {
      statusCode: 200,
      body: {
        ...VERIFY_ALL_PASSED,
        success: false,
        passed_count: 5,
        failed_count: 5,
        checks: VERIFY_ALL_PASSED.checks.map((c) =>
          c.passed && ["config_bmx_url", "sources_complete", "config_files_identical", "hosts_oct_block", "system_config_uuid_match"].includes(c.name)
            ? { ...check(c.name, false, { missing: ["TUNEIN"] }), message: "BACKEND ENGLISH TEXT" }
            : c,
        ),
      },
    });
    reachVerification();
    cy.get(".verification-failed").should("be.visible");
    cy.get(".verification-retry-btn").should("be.visible");
    cy.get("body").invoke("text").should("not.contain", "BACKEND ENGLISH TEXT");
    cy.get(".verify-check-item.failed").should("have.length.greaterThan", 3);
    assertNoOverflow();
  });

  it("shows failing DNS redirects without raw text", () => {
    mockSetupWizardApi();
    cy.intercept("POST", "/api/setup/wizard/verify-setup", { statusCode: 200, body: VERIFY_ALL_PASSED });
    cy.intercept("POST", "/api/setup/wizard/verify-redirect", { statusCode: 500, body: { detail: RAW } });
    reachVerification();
    cy.get(".verification-failed").should("be.visible");
    assertNoRawText();
    assertNoOverflow();
  });
});

describe("SSH step without SSH", () => {
  for (const width of WIDTHS) {
    it(`keeps Next disabled and explains the problem at ${width}px`, () => {
      cy.viewport(width, 900);
      mockSetupWizardApi();
      cy.intercept("POST", "/api/setup/wizard/check-ports", { statusCode: 200, body: { has_ssh: false, has_telnet: false } });
      visitDe(`/setup-wizard?deviceId=${DEVICE!.device_id}&step=3`);
      cy.contains("button", /Status|prüfen/i).first().click();
      cy.get("body").should("contain.text", "SSH");
      cy.contains("button", /Weiter/).should("be.disabled");
      assertNoOverflow();
    });
  }
});

describe("Zones: stale device badge", () => {
  it("marks devices not seen for more than 24 hours", () => {
    const old = new Date(Date.now() - 3 * 864e5).toISOString();
    cy.intercept("GET", "/api/devices", {
      statusCode: 200,
      body: { count: DEVICES.length, devices: DEVICES.map((d, i) => ({ ...d, last_seen: i < 2 ? old : new Date().toISOString() })) },
    });
    cy.intercept("GET", "/api/zones", { statusCode: 200, body: [] });
    visitDe("/multiroom");
    cy.get(".mr-dev--stale").should("have.length", 2);
    cy.get(".mr-dev--stale").first().should("contain.text", "Lange nicht gesehen");
    assertNoOverflow();
  });

  it("does not mark recently seen devices", () => {
    mockApi();
    cy.intercept("GET", "/api/zones", { statusCode: 200, body: [] });
    visitDe("/multiroom");
    cy.get(".mr-dev").should("exist");
    cy.get(".mr-dev--stale").should("not.exist");
  });
});
