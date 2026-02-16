/**
 * Custom Cypress Commands
 *
 * Note: Tests run against REAL backend API with OCT_MOCK_MODE=true
 * No more cy.intercept - backend provides mock data via MockDiscoveryAdapter
 */

/**
 * Wait for devices to load from API
 */
Cypress.Commands.add("waitForDevices", () => {
  // Wait for app to fetch devices
  cy.wait(500); // Small delay for API call
});

/**
 * Open manual IP configuration modal
 */
Cypress.Commands.add("openIPConfigModal", () => {
  cy.get("details").then(($details) => {
    if (!$details.attr("open")) {
      cy.get("details summary").click();
    }
  });
  cy.get('[data-test="manual-add-button"]').should("be.visible").click();
  cy.get('[data-test="modal-content"]').should("be.visible");
});

/**
 * Save IPs in modal
 */
Cypress.Commands.add("saveIPsInModal", (ips) => {
  cy.get('[data-test="ip-textarea"]').clear().type(ips.join(", "));
  cy.get('[data-test="save-button"]').click();
});

/**
 * Wait for modal close
 */
Cypress.Commands.add("waitForModalClose", () => {
  cy.get('[data-test="modal-content"]').should("not.exist");
});
