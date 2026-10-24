/**
 * Live responsive audit of the Restore Wizard (backup-restore path) against a real device (exploratory, not for CI).
 * Runs the "clean restore" path with REAL API calls; the backup-restore path is only
 * opened up to the backup scan screen.
 */
import { collectLayoutIssues, LayoutIssue } from "../../e2e/support/layoutAudit";

const DEVICE = "68C90B32AF6E";
const WIDTH = Number(Cypress.expose("auditWidth") ?? 320);
const LONG = { timeout: 180000 };
const RESTART_WAIT_MS = 35000; // user requirement: wait >= 30 s after restarts

const results: Record<string, LayoutIssue[]> = {};

function snap(name: string) {
  cy.wait(800);
  cy.window().then((win) => {
    results[`${name}@${WIDTH}`] = collectLayoutIssues(win);
  });
  cy.screenshot(`restore-backup-live/${name}-${WIDTH}`, { capture: "fullPage" });
}

describe("Restore wizard live audit", () => {
  after(() => {
    cy.writeFile(`tests/e2e/reports/restore-backup-live-audit-${WIDTH}.json`, results);
  });

  it("walks the backup restore path", { retries: 0, defaultCommandTimeout: 180000 }, () => {
    cy.viewport(WIDTH, 800);
    cy.visit(`/setup-wizard?deviceId=${DEVICE}&mode=restore`);
    cy.get(".wizard-choice__card", LONG).should("have.length.at.least", 2);
    snap("20-restore-choice");

    // Backup path: scan the USB stick, select the found backup set
    cy.get(".wizard-choice__card").eq(1).click();
    cy.get(".backup-scan__result", LONG).should("exist");
    snap("21-backup-scan-result");
    cy.get(".wizard-btn-next:not([disabled])", LONG).click();

    // Real execution
    cy.get(".restore-execution__progress, .restore-execution__steps", LONG).should("exist");
    snap("22-execution-running");
    cy.get(".wizard-btn-next:not([disabled])", { timeout: 600000 }).should("exist");
    snap("23-execution-done");
    cy.wait(RESTART_WAIT_MS);
    cy.get(".wizard-btn-next").click();

    // Verification (device reboots; allow time to come back)
    cy.get(".restore-verification__countdown, .restore-verification__online, .restore-verification__timeout", LONG)
      .should("exist");
    snap("24-verification-waiting");
    cy.get(".wizard-btn-next:not([disabled])", { timeout: 600000 }).should("exist");
    snap("25-verification-online");
    cy.wait(RESTART_WAIT_MS);
    cy.get(".wizard-btn-next").click();

    // Completion
    cy.get(".restore-completion", LONG).should("be.visible");
    snap("26-completion");
  });
});
