/**
 * E2E: removing an online device and finding it again with the network scan.
 * Uses the real backend with OCT_MOCK_MODE=true (MockDiscoveryAdapter returns 3 devices).
 *
 * Regression: a removed device stayed hidden after a later scan found it again (a local "removed" set was never cleared).
 */
describe("Remove an online device", () => {
  beforeEach(() => {
    const apiUrl = Cypress.expose("apiUrl");
    cy.request("DELETE", `${apiUrl}/devices`);
    cy.visit("/welcome");
    cy.get('[data-test="discover-button"]').should("be.visible").click();
    cy.waitForDevices();
    cy.get(".ds-dot").should("have.length", 3);
  });

  it("asks before removing, removes the device and shows it again after the next scan", () => {
    const card = '.ds-card-shell[data-state="current"]';

    // cancel keeps the device
    cy.get(`${card} [data-test="device-remove"]`).scrollIntoView().click();
    cy.get("dialog.dlg[role='alertdialog']").should("be.visible");
    cy.get('[data-testid="confirm-dialog-cancel"]').click();
    cy.get("dialog.dlg").should("not.exist");
    cy.get(".ds-dot").should("have.length", 3);

    // confirm removes it
    cy.get(`${card} [data-test="device-remove"]`).scrollIntoView().click();
    cy.get('[data-testid="confirm-dialog-confirm"]').click();
    cy.get(".ds-dot").should("have.length", 2);

    // the next network scan finds it again and it is visible without a reload
    cy.contains("a.nav-link", /Einstellungen|Settings/).click();
    cy.get(".st-scan").click();
    cy.get(".st-scan", { timeout: 20000 }).should("not.have.attr", "aria-busy", "true");
    cy.contains("a.nav-link", /Devices|Geräte/).click();
    cy.get(".ds-dot", { timeout: 10000 }).should("have.length", 3);
  });
});
