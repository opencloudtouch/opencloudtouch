/**
 * Custom Cypress Commands
 *
 * Note: Tests run against REAL backend API with OCT_MOCK_MODE=true
 * No more cy.intercept - backend provides mock data via MockDiscoveryAdapter
 *
 * UX Screenshot helpers:
 *   cy.screenshotDark(name)        — Screenshot mit App-Dark-Theme
 *   cy.screenshotLight(name)       — Screenshot mit weißem Analyse-Hintergrund
 *   cy.screenshotBoth(name)        — Beide Varianten (dark + light)
 *   cy.injectLightMode()           — Aktiviert hellen Analyse-Modus
 *   cy.removeLightMode()           — Entfernt hellen Analyse-Modus
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
  cy.get('[data-test="manual-add-button"]').scrollIntoView().should("be.visible").click();
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
// =============================================================================
// UX Screenshot Commands
// =============================================================================

const UX_SCREENSHOT_OPTS: Cypress.ScreenshotOptions = {
  overwrite: true,
  disableTimersAndAnimations: true,
};

const LIGHT_MODE_CSS = `
  :root {
    --color-bg-dark:        #f8f9fa !important;
    --color-bg-card:        #ffffff !important;
    --color-text-primary:   #212529 !important;
    --color-text-secondary: #6c757d !important;
    --color-border:         #dee2e6 !important;
    --color-accent:         #0055aa !important;
  }
  body, html, .app, .app-main, #root {
    background: #f8f9fa !important;
    color: #212529 !important;
  }
  .app-header, .nav, .nav-container {
    background: #e9ecef !important;
    border-bottom: 1px solid #dee2e6 !important;
  }
  .nav-link { color: #495057 !important; }
  .nav-link.active { color: #0055aa !important; }
  .device-swiper, .device-card, .preset-button, .settings-card,
  .card, .modal, .modal-content, .empty-state, .wizard-container {
    background: #ffffff !important;
    color: #212529 !important;
    border: 1px solid #dee2e6 !important;
  }
  .preset-button.assigned { background: #e8f0fe !important; color: #1a56db !important; }
  input, textarea { background: #ffffff !important; color: #212529 !important; }
  .btn-primary, button[class*="primary"] { background: #0055aa !important; color: #fff !important; }
`;

/**
 * Injiziert hellen Analyse-Modus (weißer Hintergrund für Design-Inspektion)
 */
Cypress.Commands.add("injectLightMode", () => {
  cy.document().then((doc) => {
    if (doc.getElementById("ux-light-override")) return;
    const style = doc.createElement("style");
    style.id = "ux-light-override";
    style.textContent = LIGHT_MODE_CSS;
    doc.head.appendChild(style);
  });
});

/**
 * Entfernt den hellen Analyse-Modus
 */
Cypress.Commands.add("removeLightMode", () => {
  cy.document().then((doc) => {
    doc.getElementById("ux-light-override")?.remove();
  });
});

/**
 * Screenshot mit dunklem App-Theme
 * @param name - Dateiname (ohne .png)
 */
Cypress.Commands.add("screenshotDark", (name: string) => {
  cy.screenshot(`${name}__dark`, UX_SCREENSHOT_OPTS);
});

/**
 * Screenshot mit hellem Analyse-Hintergrund
 * @param name - Dateiname (ohne .png)
 */
Cypress.Commands.add("screenshotLight", (name: string) => {
  cy.injectLightMode();
  cy.screenshot(`${name}__light`, UX_SCREENSHOT_OPTS);
  cy.removeLightMode();
});

/**
 * Nimmt Screenshot in Dark + Light Modus auf
 * @param name - Basis-Dateiname (ohne .png)
 */
Cypress.Commands.add("screenshotBoth", (name: string) => {
  cy.screenshot(`${name}__dark`, UX_SCREENSHOT_OPTS);
  cy.injectLightMode();
  cy.screenshot(`${name}__light`, UX_SCREENSHOT_OPTS);
  cy.removeLightMode();
});
