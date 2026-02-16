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
  }
}
