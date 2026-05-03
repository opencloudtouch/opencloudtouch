/**
 * Cypress E2E Support File
 * Loads custom commands
 */

// Import commands
import "./commands";

// Accessibility testing (axe-core integration)
import "cypress-axe";

// Force German locale for all E2E tests.
// The app uses navigator.language for auto-detection, which is "en" in CI
// (Ubuntu headless Chrome). Presetting "oct-lang" in localStorage before
// every page load ensures tests that assert German text pass in CI.
Cypress.on("window:before:load", (win) => {
  win.localStorage.setItem("oct-lang", "de");
});
