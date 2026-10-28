/**
 * Live responsive audit of the Setup Wizard against a real device (exploratory, not for CI).
 * Walks all steps with REAL API calls and records layout issues + screenshots per state.
 *
 * Run: ELECTRON_RUN_AS_NODE unset; npx cypress run --spec tests/real/layout/wizard-live-audit.cy.ts \
 *        --config baseUrl=http://hera:7778
 */
import { collectLayoutIssues, waitForStableLayout, LayoutIssue } from "../../e2e/support/layoutAudit";

const DEVICE = "68C90B32AF6E";
const WIDTH = Number(Cypress.expose("auditWidth") ?? 320);
const LONG = { timeout: 180000 };
const RESTART_WAIT_MS = 35000; // user requirement: wait >= 30 s after restarts

const results: Record<string, LayoutIssue[]> = {};

/** Fixed pause that is required by the device (restart time), not a synchronisation point. */
function waitForDeviceRestart() {
  cy.then({ timeout: RESTART_WAIT_MS + 10000 }, () => new Cypress.Promise((resolve) => setTimeout(resolve, RESTART_WAIT_MS)));
}

function snap(name: string) {
  cy.window().then((win) => waitForStableLayout(win));
  cy.window().then((win) => {
    results[`${name}@${WIDTH}`] = collectLayoutIssues(win);
  });
  cy.screenshot(`wizard-live/${name}-${WIDTH}`, { capture: "fullPage" });
}

describe("Setup wizard live audit", () => {
  after(() => {
    cy.writeFile(`tests/e2e/reports/wizard-live-audit-${WIDTH}.json`, results);
  });

  it("walks the full setup wizard", { retries: 0, defaultCommandTimeout: 180000 }, () => {
    cy.viewport(WIDTH, 800);
    cy.visit(`/setup-wizard?deviceId=${DEVICE}`);
    cy.get(".wizard-choice__card--setup, .wizard-choice__card", LONG).should("exist");
    snap("00-choice");
    cy.get(".wizard-choice__card").first().click();

    // Step 2: USB preparation
    cy.get(".usb-platform-select", LONG).should("be.visible");
    snap("02-usb");
    cy.get('input[type="checkbox"]').last().scrollIntoView().should("be.visible").check();
    cy.get(".wizard-btn-next").click();

    // Step 3: power cycle / ports / SSH decision
    cy.get(".power-cycle-check-btn", LONG).should("be.visible");
    snap("03-ports-before");
    cy.get(".power-cycle-check-btn").click();
    cy.get(".ssh-risk-assessment", LONG).should("exist");
    cy.get(".risk-question").each(($q) => {
      cy.wrap($q).find(".risk-answer-btn").first().click();
    });
    cy.get(".risk-card--temporary", LONG).click();
    snap("03-ports-after");
    cy.get(".wizard-btn-next").should("not.be.disabled").click();

    // Step 4: backup
    cy.get(".backup-create-btn", LONG).should("be.visible");
    snap("04-backup-before");
    cy.get(".backup-create-btn").click();
    // Backup can take several minutes on a real device (user decision: allow 10 min).
    cy.get(".wizard-btn-next:not([disabled])", { timeout: 600000 }).should("exist");
    snap("04-backup-after");
    cy.get(".wizard-btn-next").click();

    // Step 5: config modification
    cy.get(".config-modify-btn", LONG).should("be.visible");
    snap("05-config-before");
    cy.get(".config-modify-btn").click();
    cy.get(".wizard-btn-next:not([disabled])", LONG).should("exist");
    snap("05-config-after");
    cy.get(".wizard-btn-next").click();

    // Step 6: hosts
    cy.get(".hosts-modify-btn", LONG).should("be.visible");
    snap("06-hosts-before");
    cy.get(".hosts-modify-btn").click();
    cy.get(".wizard-btn-next:not([disabled])", LONG).should("exist");
    snap("06-hosts-after");
    cy.get(".wizard-btn-next").click();

    // Step 7: NTP
    cy.get(".ntp-patch-btn", LONG).should("be.visible");
    snap("07-ntp-before");
    cy.get(".ntp-patch-btn").click();
    cy.get(".wizard-btn-next:not([disabled])", LONG).should("exist");
    snap("07-ntp-after");
    cy.get(".wizard-btn-next").click();

    // Step 8: finalize, reboot, verify (restart waits >= 30 s)
    cy.contains("button", /Finalize|Abschlie/i, LONG).should("be.visible");
    snap("08-verify-before");
    cy.contains("button", /Finalize|Abschlie/i).click();
    cy.get(".reboot-btn", LONG).should("be.visible");
    snap("08-verify-reboot");
    cy.get(".reboot-btn").click();
    waitForDeviceRestart();
    snap("08-verify-rebooting");
    cy.get(".verification-test-btn", { timeout: 240000 }).should("be.visible");
    waitForDeviceRestart();
    cy.get(".verification-test-btn").click();
    cy.get(".wizard-btn-next:not([disabled])", { timeout: 240000 }).should("exist");
    snap("08-verify-after");
    cy.get(".wizard-btn-next").click();

    // Step 9: completion
    cy.get(".completion-btn-done", LONG).should("be.visible");
    snap("09-completion");
  });
});
