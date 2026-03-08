/**
 * TypeScript Declarations for Custom Cypress Commands
 */

/// <reference types="cypress" />

declare namespace Cypress {
  interface Chainable {
    /**
     * Wait for devices to load from API
     * @example cy.waitForDevices()
     */
    waitForDevices(): Chainable<void>;

    /**
     * Open manual IP configuration modal
     * @example cy.openIPConfigModal()
     */
    openIPConfigModal(): Chainable<void>;

    /**
     * Save IPs in modal
     * @param ips - Array of IP addresses to save
     * @example cy.saveIPsInModal(['192.168.1.100', '192.168.1.101'])
     */
    saveIPsInModal(ips: string[]): Chainable<void>;

    /**
     * Wait for modal to close
     * @example cy.waitForModalClose()
     */
    waitForModalClose(): Chainable<void>;

    // =========================================================================
    // UX Screenshot Commands
    // =========================================================================

    /**
     * Inject light/white background CSS for design inspection screenshots.
     * Overrides the dark Bose theme with a neutral light analysis mode.
     * @example cy.injectLightMode()
     */
    injectLightMode(): Chainable<void>;

    /**
     * Remove the injected light mode CSS override.
     * @example cy.removeLightMode()
     */
    removeLightMode(): Chainable<void>;

    /**
     * Take a screenshot with the native dark app theme.
     * Screenshot is saved as `{name}__dark.png`.
     * @param name - Base filename (without extension)
     * @example cy.screenshotDark('02a_presets_full-page')
     */
    screenshotDark(name: string): Chainable<void>;

    /**
     * Take a screenshot with an injected light/white background.
     * Useful for isolated component inspection.
     * Screenshot is saved as `{name}__light.png`.
     * @param name - Base filename (without extension)
     * @example cy.screenshotLight('02a_presets_full-page')
     */
    screenshotLight(name: string): Chainable<void>;

    /**
     * Take two screenshots: one with dark theme, one with light background.
     * Saves `{name}__dark.png` and `{name}__light.png`.
     * @param name - Base filename (without extension)
     * @example cy.screenshotBoth('02a_presets_full-page')
     */
    screenshotBoth(name: string): Chainable<void>;
  }
}
