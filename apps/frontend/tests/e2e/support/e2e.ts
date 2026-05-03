/**
 * Cypress E2E Support File
 * Loads custom commands
 */

// Import commands
import "./commands";

// Accessibility testing (axe-core integration)
import "cypress-axe";

// Default to German locale for all E2E tests.
// The app uses navigator.language for auto-detection, which is "en" in CI
// (Ubuntu headless Chrome). Presetting "oct-lang" in localStorage before
// every page load ensures most tests run in German, matching their assertions.
//
// Individual specs can opt out by calling `Cypress.env("e2e_locale", "en")`
// in their beforeEach (see wizard-i18n.cy.ts which tests English as default).
Cypress.on("window:before:load", (win) => {
  const locale = (Cypress.env("e2e_locale") as string | undefined) ?? "de";
  win.localStorage.setItem("oct-lang", locale);
});
