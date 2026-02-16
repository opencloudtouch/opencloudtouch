/**
 * Real Device E2E Tests - Device Control
 * Requires REAL Bose SoundTouch devices (OCT_MOCK_MODE=false)
 *
 * Prerequisites:
 * - Backend running with OCT_MOCK_MODE=false
 * - At least 1 real SoundTouch device on network
 * - Device powered on and reachable
 *
 * Run with: npm run test:e2e:real (or scripts/run-real-tests.ps1)
 */
describe("Device Control - Real Hardware", () => {
  before(() => {
    // Verify we're NOT in mock mode
    const apiUrl = Cypress.env("apiUrl");
    cy.request("GET", `${apiUrl}/../health`)
      .its("body")
      .then((health) => {
        expect(health.mock_mode).to.be.false;
      });
  });

  beforeEach(() => {
    // Clear DB before each test
    const apiUrl = Cypress.env("apiUrl");
    cy.request("DELETE", `${apiUrl}/devices`);
  });

  describe("Real Device Discovery", () => {
    it("should discover actual devices from network", () => {
      cy.visit("/welcome");

      // Trigger discovery (will use SSDP + Manual IPs)
      cy.get('[data-test="discover-button"]').click();

      // Wait for real discovery (might take longer than mocks)
      cy.wait(15000); // Real SSDP can take 10s+

      // Should redirect to dashboard with real devices
      cy.url().should("eq", Cypress.config().baseUrl + "/");
      cy.get('[data-test="app-header"]').should("be.visible");

      // Verify at least 1 device found
      cy.get('[data-test="device-card"]').should("exist");

      // Verify device has REAL data (not mock names)
      cy.get('[data-test="device-card"]').within(() => {
        cy.get('[data-test="device-name"]').should("not.be.empty");
        cy.get('[data-test="device-ip"]').should("match", /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/);
      });
    });

    it("should verify discovered devices have valid IP addresses", () => {
      const apiUrl = Cypress.env("apiUrl");

      cy.visit("/welcome");
      cy.get('[data-test="discover-button"]').click();
      cy.wait(15000); // Wait for real discovery

      // Check devices via API
      cy.request("GET", `${apiUrl}/devices`).then((response) => {
        expect(response.body.count).to.be.greaterThan(0);

        response.body.devices.forEach((device) => {
          // Verify IP format
          expect(device.ip).to.match(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/);

          // Verify device has real data
          expect(device.device_id).to.not.be.empty;
          expect(device.name).to.not.be.empty;
          expect(device.model).to.not.be.empty;

          // Verify NOT mock device IDs
          expect(device.device_id).to.not.match(/^AABBCC|^DDEEFF|^112233/);
        });
      });
    });
  });

  describe("Real Device Interaction", () => {
    beforeEach(() => {
      // Setup: Discover real devices first
      const apiUrl = Cypress.env("apiUrl");
      cy.request("POST", `${apiUrl}/devices/sync`);
      cy.wait(15000); // Wait for sync

      cy.visit("/");
    });

    it("should display actual device information", () => {
      // Verify device card shows real data
      cy.get('[data-test="device-card"]').should("be.visible");

      cy.get('[data-test="device-card"]').within(() => {
        // Name should NOT be mock names
        cy.get('[data-test="device-name"]')
          .invoke("text")
          .should((name) => {
            expect(name).to.not.match(/Living Room|Kitchen|Bedroom/);
          });

        // IP should be valid
        cy.get('[data-test="device-ip"]')
          .invoke("text")
          .should((ip) => {
            expect(ip).to.match(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/);
            expect(ip).to.not.equal("192.168.1.100"); // Not mock IP
          });
      });
    });

    it("should handle real device that is offline", () => {
      // Note: This test requires manually powering off a device
      // Skip if not testing offline scenarios
      cy.log("⚠️  To test offline handling: Power off a device and re-run");

      // Try to discover - might find fewer devices
      const apiUrl = Cypress.env("apiUrl");
      cy.request("POST", `${apiUrl}/devices/sync`);
      cy.wait(15000);

      // Should still load dashboard even if some devices offline
      cy.visit("/");
      cy.get('[data-test="app-header"]').should("be.visible");
    });
  });
});
