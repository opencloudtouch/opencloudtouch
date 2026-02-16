/**
 * E2E Tests: Preset Mapping (Iteration 3)
 * Tests preset assignment workflow: Search station → Assign to preset → Verify persistence
 *
 * Prerequisites:
 * - Backend running with OCT_MOCK_MODE=true
 * - MockDiscoveryAdapter returns 3 predefined devices
 * - RadioBrowser API available (real or mocked)
 */
describe("Preset Mapping (Iteration 3)", () => {
  const apiUrl = Cypress.env("apiUrl");
  let deviceId: string;

  beforeEach(() => {
    // Clear devices and presets before each test
    cy.request("DELETE", `${apiUrl}/devices`);

    // Discover devices (MockDiscoveryAdapter returns 3 devices)
    cy.visit("/welcome");
    cy.get('[data-test="discover-button"]').click();
    cy.waitForDevices();

    // Get first device ID for preset tests
    cy.request(`${apiUrl}/devices`).then((response) => {
      deviceId = response.body.devices[0].device_id;
      // Clear any existing presets for this device
      cy.request("GET", `${apiUrl}/presets/${deviceId}`).then((presetsResp) => {
        presetsResp.body.forEach((preset: { preset_number: number }) => {
          cy.request("DELETE", `${apiUrl}/presets/${deviceId}/${preset.preset_number}`);
        });
      });
    });
  });

  describe("Error Handling", () => {
    it("should validate preset number (1-6 only)", () => {
      // Directly test API endpoint with invalid preset number
      cy.request({
        method: "POST",
        url: `${apiUrl}/presets/set`,
        failOnStatusCode: false,
        body: {
          device_id: deviceId,
          preset_number: 7, // Invalid (must be 1-6)
          station_uuid: "test-uuid",
          station_name: "Test Station",
          station_url: "http://test.com/stream",
        },
      }).then((response) => {
        expect(response.status).to.eq(422); // Validation error
      });
    });

    it("should handle backend errors gracefully", () => {
      // Mock a backend error by requesting with invalid data
      cy.request({
        method: "POST",
        url: `${apiUrl}/presets/set`,
        failOnStatusCode: false,
        body: {
          device_id: deviceId,
          preset_number: 1,
          // Missing required fields → should fail
        },
      }).then((response) => {
        expect(response.status).to.be.greaterThan(399); // 4xx or 5xx error
      });
    });
  });

  describe("Multi-Device Presets", () => {
    it("should manage presets independently for different devices", () => {
      // Get second device ID
      cy.request(`${apiUrl}/devices`).then((response) => {
        const device1Id = response.body.devices[0].device_id;
        const device2Id = response.body.devices[1].device_id;

        // Assign preset 1 to device 1
        cy.request("POST", `${apiUrl}/presets/set`, {
          device_id: device1Id,
          preset_number: 1,
          station_uuid: "station-a",
          station_name: "Station A",
          station_url: "http://a.com/stream",
        });

        // Assign preset 1 to device 2 (different station)
        cy.request("POST", `${apiUrl}/presets/set`, {
          device_id: device2Id,
          preset_number: 1,
          station_uuid: "station-b",
          station_name: "Station B",
          station_url: "http://b.com/stream",
        });

        // Verify both devices have different preset 1
        cy.request(`${apiUrl}/presets/${device1Id}`).then((resp1) => {
          cy.request(`${apiUrl}/presets/${device2Id}`).then((resp2) => {
            expect(resp1.body[0].station_name).to.eq("Station A");
            expect(resp2.body[0].station_name).to.eq("Station B");
            expect(resp1.body[0].station_uuid).to.not.eq(resp2.body[0].station_uuid);
          });
        });
      });
    });
  });
});
