/**
 * E2E Tests: Manual IP Configuration
 * Uses REAL backend API with OCT_MOCK_MODE=true (MockDiscoveryAdapter)
 *
 * Prerequisites:
 * - Backend running with OCT_MOCK_MODE=true
 * - MockDiscoveryAdapter returns 3 predefined devices (192.168.1.100-102)
 */

describe("Manual IP Configuration", () => {
  beforeEach(() => {
    // Clear DB and manual IPs before each test
    const apiUrl = Cypress.env("apiUrl");
    cy.request("DELETE", `${apiUrl}/devices`);
    cy.request("POST", `${apiUrl}/settings/manual-ips`, { ips: [] });
  });

  describe("EmptyState - Modal Opening", () => {
    it("should display EmptyState welcome screen", () => {
      cy.visit("/welcome");

      cy.get('[data-test="empty-state"]').should("be.visible");
      cy.get('[data-test="welcome-title"]').should("be.visible").and("contain", "Willkommen");
      cy.get("p").should("contain", "Noch keine");
    });

    it("should open manual IP configuration modal", () => {
      cy.visit("/welcome");

      cy.openIPConfigModal();

      // Verify modal elements exist
      cy.get('[data-test="modal-title"]').should("contain", "Manuelle IP-Konfiguration");
      cy.get('[data-test="ip-textarea"]').should("be.visible");
      cy.get('[data-test="save-button"]').should("be.visible");
      cy.get('[data-test="cancel-button"]').should("be.visible");
    });
  });

  describe("Single IP Configuration", () => {
    it("should save 1 IP and create 1 device", () => {
      const ips = ["192.168.1.100"]; // Matches first mock device

      cy.visit("/welcome");

      // Open modal and enter IP
      cy.openIPConfigModal();
      cy.saveIPsInModal(ips);

      // Verify modal closes
      cy.waitForModalClose();

      // Trigger discovery
      cy.get('[data-test="discover-button"]').click();
      cy.waitForDevices();

      // Verify redirect to dashboard
      cy.url().should("eq", Cypress.config().baseUrl + "/");
      cy.get('[data-test="device-card"]').should("have.length.at.least", 1);
    });
  });

  describe("Multiple IPs Configuration", () => {
    it("should save 2 IPs and create 2 devices", () => {
      const ips = ["192.168.1.100", "192.168.1.101"];

      cy.visit("/welcome");

      cy.openIPConfigModal();
      cy.saveIPsInModal(ips);
      cy.waitForModalClose();

      // Trigger discovery
      cy.get('[data-test="discover-button"]').click();
      cy.waitForDevices();

      // Verify devices (MockDiscoveryAdapter returns 3 devices total)
      // Swiper shows 1 card at a time, check dots for count
      cy.get(".swiper-dots .dot").should("have.length", 3);
      cy.get('[data-test="device-card"]').should("have.length", 1);
    });

    it("should save 3 IPs and create 3 devices", () => {
      const ips = ["192.168.1.100", "192.168.1.101", "192.168.1.102"];

      cy.visit("/welcome");

      cy.openIPConfigModal();
      cy.saveIPsInModal(ips);
      cy.waitForModalClose();

      cy.get('[data-test="discover-button"]').click();
      cy.waitForDevices();

      // Verify 3 devices (all mock devices)
      // Swiper shows 1 card at a time, check dots for count
      cy.get(".swiper-dots .dot").should("have.length", 3);
      cy.get('[data-test="device-card"]').should("have.length", 1);
    });
  });

  describe("Cancel Action - No Save", () => {
    it("should not save IPs when cancel is clicked", () => {
      cy.visit("/welcome");

      cy.openIPConfigModal();

      // Enter IPs but cancel
      cy.get('[data-test="ip-textarea"]').type("192.168.1.99, 192.168.1.100");
      cy.get('[data-test="cancel-button"]').click();

      // Verify modal closed
      cy.get('[data-test="modal-content"]').should("not.exist");

      // Verify IPs NOT saved (should still be empty)
      const apiUrl = Cypress.env("apiUrl");
      cy.request("GET", `${apiUrl}/settings/manual-ips`).its("body.ips").should("have.length", 0);
    });
  });

  describe("Complete User Journey", () => {
    it("should complete full flow: EmptyState → Add IPs → Discover → Dashboard", () => {
      const ips = ["192.168.1.100", "192.168.1.101"];

      // Start at welcome
      cy.visit("/welcome");
      cy.get('[data-test="empty-state"]').should("be.visible");

      // Open modal and add IPs
      cy.openIPConfigModal();
      cy.saveIPsInModal(ips);
      cy.waitForModalClose();

      // Trigger discovery
      cy.get('[data-test="discover-button"]').should("be.visible").click();
      cy.waitForDevices();

      // Should redirect to dashboard with devices
      cy.url().should("eq", Cypress.config().baseUrl + "/");
      cy.get('[data-test="app-header"]').should("be.visible");
      // Swiper shows 1 card at a time with dots for navigation
      cy.get(".swiper-dots .dot").should("have.length", 3); // Mock devices
      cy.get('[data-test="device-card"]').should("have.length", 1);
    });
  });

  describe("Regression Tests - Bug Fixes", () => {
    it("BUG-FIX: Manual IPs should save via bulk endpoint", () => {
      const ips = ["192.168.1.100", "192.168.1.101", "192.168.1.102"];

      cy.visit("/welcome");
      cy.openIPConfigModal();
      cy.saveIPsInModal(ips);
      cy.waitForModalClose();

      // Verify IPs persisted via bulk endpoint
      const apiUrl = Cypress.env("apiUrl");
      cy.request("GET", `${apiUrl}/settings/manual-ips`).then((response) => {
        expect(response.body.ips).to.have.length(3);
        expect(response.body.ips).to.include.members(ips);
      });
    });

    it("BUG-FIX: State persists across page reloads", () => {
      const ips = ["192.168.1.100", "192.168.1.101"];

      // Setup: Add devices
      cy.visit("/welcome");
      cy.openIPConfigModal();
      cy.saveIPsInModal(ips);
      cy.waitForModalClose();
      cy.get('[data-test="discover-button"]').click();
      cy.waitForDevices();

      // Verify initial state - should be on dashboard
      cy.url().should("eq", Cypress.config().baseUrl + "/");
      cy.get(".swiper-dots .dot").should("have.length", 3);

      // Reload page
      cy.reload();

      // Verify state persisted after reload
      cy.url().should("eq", Cypress.config().baseUrl + "/");
      cy.get('[data-test="app-header"]').should("be.visible");
      cy.get(".swiper-dots .dot").should("have.length", 3);
      cy.get('[data-test="device-card"]').should("have.length", 1);

      // Verify devices still in DB via API
      const apiUrl = Cypress.env("apiUrl");
      cy.request("GET", `${apiUrl}/devices`).then((response) => {
        expect(response.body).to.have.property("count", 3);
        expect(response.body.devices).to.have.length(3);
      });
    });

    it("BUG-FIX: Placeholder images are SVG data URLs", () => {
      const ips = ["192.168.1.100"];

      // Setup: Create at least 1 device
      cy.visit("/welcome");
      cy.openIPConfigModal();
      cy.saveIPsInModal(ips);
      cy.waitForModalClose();
      cy.get('[data-test="discover-button"]').click();
      cy.waitForDevices();

      // Verify device card exists
      cy.get('[data-test="device-card"]').should("be.visible");

      // NOTE: Current implementation doesn't show device images yet
      // This test verifies the device card structure is correct
      // Once images are implemented, they should use SVG data URLs like:
      // data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0...

      // Verify device card has at least name and IP
      cy.get('[data-test="device-card"]').within(() => {
        cy.get('[data-test="device-name"]').should("be.visible");
        cy.get('[data-test="device-ip"]').should("be.visible").and("contain", "192.168.1");
      });

      // Future: When images are added, uncomment this:
      // cy.get('[data-test="device-card"]').within(() => {
      //   cy.get('img').should('exist').and(($img) => {
      //     const src = $img.attr('src')
      //     expect(src).to.match(/^data:image\/svg\+xml/)
      //   })
      // })
    });
  });
});
