/**
 * Real Device E2E Tests - Radio Playback
 * Requires REAL Bose SoundTouch devices (OCT_MOCK_MODE=false)
 *
 * Prerequisites:
 * - Backend running with OCT_MOCK_MODE=false
 * - At least 1 real SoundTouch device on network
 * - Device powered on and supports INTERNET_RADIO source
 *
 * Run with: npm run test:e2e:real (or scripts/run-real-tests.ps1)
 */
describe("Radio Playback - Real Hardware", () => {
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
    // Setup: Ensure devices are discovered
    const apiUrl = Cypress.env("apiUrl");
    cy.request("DELETE", `${apiUrl}/devices`);
    cy.request("POST", `${apiUrl}/devices/sync`);
    cy.wait(15000); // Wait for real discovery

    cy.visit("/");
  });

  describe("Radio Search Integration", () => {
    it("should search radio stations via RadioBrowser API", () => {
      cy.visit("/radio");

      // Wait for page load
      cy.get('[data-test="radio-search-input"]').should("be.visible");

      // Search for actual radio station
      cy.get('[data-test="radio-search-input"]').type("BBC Radio 1");
      cy.get('[data-test="radio-search-button"]').click();

      // Should get real results from RadioBrowser API
      cy.wait(3000); // API might be slow

      // Verify results are NOT mock data
      cy.get('[data-test="radio-station-result"]').should("have.length.greaterThan", 0);

      cy.get('[data-test="radio-station-result"]')
        .first()
        .within(() => {
          // Real station should have these fields
          cy.get('[data-test="station-name"]').should("not.be.empty");
          cy.get('[data-test="station-country"]').should("not.be.empty");
        });
    });

    it("should handle network errors from RadioBrowser API gracefully", () => {
      // Note: This test might fail if RadioBrowser is actually down
      cy.visit("/radio");

      // Search with very obscure term that likely returns 0 results
      cy.get('[data-test="radio-search-input"]').type("xyznonexistentstation12345");
      cy.get('[data-test="radio-search-button"]').click();

      cy.wait(3000);

      // Should show "no results" message, NOT crash
      cy.get('[data-test="no-results-message"]').should("be.visible");
    });
  });

  describe("Device Capabilities Detection", () => {
    it("should detect actual device capabilities from real hardware", () => {
      const apiUrl = Cypress.env("apiUrl");

      // Get devices
      cy.request("GET", `${apiUrl}/devices`).then((response) => {
        expect(response.body.count).to.be.greaterThan(0);

        const deviceId = response.body.devices[0].device_id;

        // Get capabilities
        cy.request("GET", `${apiUrl}/devices/${deviceId}/capabilities`).then((capResp) => {
          const capabilities = capResp.body;

          // Verify capabilities structure
          expect(capabilities).to.have.property("hdmi_control");
          expect(capabilities).to.have.property("supports_bluetooth");
          expect(capabilities).to.have.property("supports_airplay");

          // Log what device actually supports
          cy.log(
            `Device capabilities: HDMI=${capabilities.hdmi_control}, BT=${capabilities.supports_bluetooth}, AirPlay=${capabilities.supports_airplay}`
          );
        });
      });
    });
  });
});
