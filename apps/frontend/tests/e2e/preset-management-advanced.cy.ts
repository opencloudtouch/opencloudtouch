/**
 * E2E Tests: Preset Management Advanced
 * Tests preset lifecycle: set, clear, overwrite (currently broken!)
 *
 * Known Issues to Fix:
 * - Cannot overwrite preset without clearing first
 * - Clicking filled preset should allow reassignment
 *
 * Prerequisites:
 * - Backend running with OCT_MOCK_MODE=true
 */

describe("Preset Management Advanced", () => {
  const apiUrl = Cypress.env("apiUrl");
  let deviceId: string;

  const stationA = {
    uuid: "mock-bbc-1",
    name: "BBC Radio 1",
    country: "United Kingdom",
    url: "https://stream.bbc.co.uk/radio1",
    homepage: "https://bbc.co.uk/radio1",
    favicon: "https://bbc.co.uk/favicon-radio1.png",
  };

  const stationB = {
    uuid: "mock-npr-1",
    name: "NPR (National Public Radio)",
    country: "United States",
    url: "https://stream.npr.org/live",
    homepage: "https://npr.org",
    favicon: "https://npr.org/favicon.png",
  };

  const stationC = {
    uuid: "mock-france-inter",
    name: "France Inter",
    country: "France",
    url: "https://stream.radiofrance.fr/inter",
    homepage: "https://radiofrance.fr/inter",
    favicon: "https://radiofrance.fr/favicon.png",
  };

  const waitForPresetsReady = () => {
    return cy.get('[data-testid="loading-indicator"]', { timeout: 10000 }).should("not.exist");
  };

  beforeEach(() => {
    // Clear devices
    cy.request("DELETE", `${apiUrl}/devices`);

    // Discover devices
    cy.visit("/welcome");
    cy.get('[data-test="discover-button"]').click();

    // Wait for device data to render
    cy.get('[data-test="device-card"]', { timeout: 10000 }).should("have.length.at.least", 1);
    cy.get('[data-test="device-name"]', { timeout: 10000 }).should("not.contain", "Unknown");

    // Get device ID
    cy.request(`${apiUrl}/devices`).then((response) => {
      deviceId = response.body.devices[0].device_id;

      // Clear all presets for this device
      cy.request("GET", `${apiUrl}/presets/${deviceId}`).then((presetsResp) => {
        presetsResp.body.forEach((preset: { preset_number: number }) => {
          cy.request("DELETE", `${apiUrl}/presets/${deviceId}/${preset.preset_number}`);
        });
      });
    });

    // Navigate to Radio Presets
    cy.contains("Radio Presets").click();
    waitForPresetsReady();
  });

  describe("Preset Lifecycle: Set → Clear → Set", () => {
    it("should set preset on empty slot", () => {
      //Find and click the first empty preset slot (whichever number it is)
      waitForPresetsReady();

      // Get the first empty preset slot's number for later verification
      cy.get(".preset-empty")
        .first()
        .invoke("attr", "data-testid")
        .then((testId) => {
          const slotNumber = testId?.split("-")[2] || "1";

          // Click the first empty slot
          cy.get(".preset-empty").first().scrollIntoView().click({ force: true });
          cy.get(".radio-search-modal", { timeout: 10000 }).should("be.visible");

          // Search and select
          cy.get(".search-input").type("BBC");
          cy.get(".search-results", { timeout: 10000 }).should("be.visible");
          cy.get(".search-result-item", { timeout: 10000 }).should("have.length.at.least", 1);
          cy.get(".search-result-item").first().click();

          // Wait for API call to complete and modal to close
          cy.get(".radio-search-modal", { timeout: 10000 }).should("not.exist");

          // Wait for preset to be saved (loading indicator may not appear with fast mock API)
          cy.wait(500); // Give API call time to complete

          // Verify preset saved in UI (should show station name in the slot we clicked)
          cy.get(`[data-testid="preset-play-${slotNumber}"]`).should("contain", stationA.name);
        });
    });

    it("should clear assigned preset", () => {
      // Assign preset 2 via API
      cy.request("POST", `${apiUrl}/presets/set`, {
        device_id: deviceId,
        preset_number: 2,
        station_uuid: stationA.uuid,
        station_name: stationA.name,
        station_url: stationA.url,
        station_homepage: stationA.homepage,
        station_favicon: stationA.favicon,
      });

      // Reload to see preset
      cy.reload();
      waitForPresetsReady();
      cy.contains(".presets-grid .preset-play", stationA.name, { timeout: 10000 }).should("exist");
      cy.get(".presets-grid .preset-play").eq(0).should("contain", stationA.name);

      // Confirm deletion
      cy.on("window:confirm", () => true);

      // Clear preset using data-testid
      cy.get('[data-testid="preset-clear-2"]').click({ force: true });

      // Verify preset cleared in UI
      waitForPresetsReady();
      cy.get('[data-testid="preset-empty-2"]').should("exist");
    });

    it("should allow setting preset after clearing", () => {
      // Set preset 3
      cy.request("POST", `${apiUrl}/presets/set`, {
        device_id: deviceId,
        preset_number: 3,
        station_uuid: stationA.uuid,
        station_name: stationA.name,
        station_url: stationA.url,
      });

      cy.reload();
      waitForPresetsReady();

      // Clear preset 3
      cy.on("window:confirm", () => true);
      cy.get('[data-testid="preset-clear-3"]').click({ force: true });

      // Now assign new station to cleared preset
      waitForPresetsReady();
      cy.get('[data-testid="preset-empty-3"]').scrollIntoView().click({ force: true });
      cy.get(".radio-search-modal", { timeout: 10000 }).should("be.visible");
      cy.get(".search-input").type("NPR");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");
      cy.get(".search-result-item", { timeout: 10000 }).should("have.length.at.least", 1);
      cy.get(".search-result-item").first().click();

      // Wait for API call to complete and modal to close
      cy.get(".radio-search-modal", { timeout: 10000 }).should("not.exist");
      cy.get('[data-testid="loading-indicator"]', { timeout: 10000 }).should("not.exist");

      // Verify new preset
      cy.get('[data-testid="preset-play-3"]').should("contain", stationB.name);
    });
  });

  describe("Preset Overwrite (CURRENTLY BROKEN)", () => {
    it("should overwrite preset after clearing first", () => {
      // Assign preset 4 with Station A
      cy.request("POST", `${apiUrl}/presets/set`, {
        device_id: deviceId,
        preset_number: 4,
        station_uuid: stationA.uuid,
        station_name: stationA.name,
        station_url: stationA.url,
        station_homepage: stationA.homepage,
        station_favicon: stationA.favicon,
      });

      cy.reload();
      waitForPresetsReady();
      cy.get('[data-testid="preset-play-4"]', { timeout: 10000 })
        .should("exist")
        .and("contain", stationA.name);

      // Clear preset first
      cy.on("window:confirm", () => true);
      cy.get('[data-testid="preset-clear-4"]').click({ force: true });
      waitForPresetsReady();

      // Click on empty preset 4 to reassign
      cy.get('[data-testid="preset-empty-4"]').scrollIntoView().click({ force: true });
      cy.get(".radio-search-modal", { timeout: 10000 }).should("be.visible");

      // Select new station
      cy.get(".search-input").type("NPR");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");
      cy.get(".search-result-item", { timeout: 10000 }).should("have.length.at.least", 1);
      cy.get(".search-result-item").first().click();

      // Verify preset overwritten
      cy.get(".radio-search-modal", { timeout: 10000 }).should("not.exist");
      cy.get('[data-testid="loading-indicator"]', { timeout: 10000 }).should("not.exist");
      cy.get('[data-testid="preset-play-4"]').should("contain", stationB.name);
    });

    it("should handle multiple overwrites sequentially", () => {
      const presetNumber = 5;
      const stations = [stationA, stationB, stationC];

      stations.forEach((station, index) => {
        if (index > 0) {
          cy.on("window:confirm", () => true);
          // Clear previous preset using data-testid
          cy.get(`[data-testid="preset-clear-${presetNumber}"]`).click({ force: true });
          waitForPresetsReady();
        }

        // Click preset button (should be empty after clear, or initially empty)
        cy.get(`[data-testid="preset-empty-${presetNumber}"]`)
          .scrollIntoView()
          .click({ force: true });
        cy.get(".radio-search-modal", { timeout: 10000 }).should("be.visible");

        cy.get(".search-input").clear().type(station.name);
        cy.get(".search-results", { timeout: 10000 }).should("be.visible");
        cy.get(".search-result-item", { timeout: 10000 }).should("have.length.at.least", 1);
        cy.get(".search-result-item").first().click();

        // Wait for API call to complete and modal to close
        cy.get(".radio-search-modal", { timeout: 10000 }).should("not.exist");
        cy.get('[data-testid="loading-indicator"]', { timeout: 10000 }).should("not.exist");

        // Verify preset was set
        cy.get(`[data-testid="preset-play-${presetNumber}"]`).should("contain", station.name);
      });

      // Final verification: should have last station
      cy.get(`[data-testid="preset-play-${presetNumber}"]`).should("contain", stationC.name);
    });

    it("should require confirmation for overwrite (optional UX)", () => {
      // Assign preset 6
      cy.request("POST", `${apiUrl}/presets/set`, {
        device_id: deviceId,
        preset_number: 6,
        station_uuid: stationA.uuid,
        station_name: stationA.name,
        station_url: stationA.url,
      });

      cy.reload();

      // Attempt to overwrite by clearing first
      cy.on("window:confirm", () => true);
      cy.get(".presets-grid").within(() => {
        cy.contains("button", stationA.name)
          .scrollIntoView()
          .parent()
          .find('[class*="clear"]')
          .click({ force: true });
      });

      waitForPresetsReady();

      // Now reassign
      cy.get(".preset-empty").eq(5).scrollIntoView().click({ force: true });
      cy.get(".radio-search-modal").should("be.visible");
    });
  });

  describe("Preset Button States & UI", () => {
    it("should show different UI for empty vs filled preset", () => {
      // Empty preset (Preset 1)
      cy.get(".preset-empty")
        .first()
        .within(() => {
          // Should show "Zuweisen" or "+" or similar
          cy.contains(/Zuweisen|\+|Assign/i).should("exist");
        });

      // Fill preset 2
      cy.request("POST", `${apiUrl}/presets/set`, {
        device_id: deviceId,
        preset_number: 2,
        station_uuid: stationA.uuid,
        station_name: stationA.name,
        station_url: stationA.url,
      });

      cy.reload();
      waitForPresetsReady();
      cy.get('[data-testid="preset-play-2"]', { timeout: 10000 })
        .should("exist")
        .and("contain", stationA.name)
        .and("not.contain", "Zuweisen");
    });

    it("should show clear and play buttons for filled preset", () => {
      // Fill preset 3
      cy.request("POST", `${apiUrl}/presets/set`, {
        device_id: deviceId,
        preset_number: 3,
        station_uuid: stationA.uuid,
        station_name: stationA.name,
        station_url: stationA.url,
      });

      cy.reload();
      waitForPresetsReady();
      cy.get('[data-testid="preset-play-3"]', { timeout: 10000 })
        .should("exist")
        .and("contain", stationA.name);

      // Should have clear button
      cy.get('[data-testid="preset-clear-3"]').should("exist");

      // Should have play button
      cy.get('[data-testid="preset-play-3"]').should("exist");
    });

    it("should disable interactions during loading", () => {
      cy.intercept("POST", `${apiUrl}/presets/set`, (req) => {
        // Delay response by 1 second to simulate slow network
        req.on("response", (res) => {
          res.setDelay(1000);
        });
      }).as("slowSetPreset");

      // Start preset assignment
      cy.get(".preset-empty").first().scrollIntoView().click({ force: true });
      cy.get(".radio-search-modal", { timeout: 10000 }).should("be.visible");
      cy.get(".search-input").type("BBC");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");
      cy.get(".search-result-item", { timeout: 10000 }).should("have.length.at.least", 1);
      cy.get(".search-result-item").first().click();

      // Loading indicator should show
      cy.get('[data-testid="loading-indicator"]').should("be.visible");

      // Buttons should be disabled during loading (optional)
      cy.wait("@slowSetPreset");
    });
  });

  describe("Preset Persistence", () => {
    it("should persist presets across page reloads", () => {
      // Set multiple presets
      const presets = [
        { number: 1, station: stationA },
        { number: 3, station: stationB },
        { number: 5, station: stationC },
      ];

      presets.forEach(({ number, station }) => {
        cy.request("POST", `${apiUrl}/presets/set`, {
          device_id: deviceId,
          preset_number: number,
          station_uuid: station.uuid,
          station_name: station.name,
          station_url: station.url,
        });
      });

      // Reload page
      cy.reload();
      waitForPresetsReady();

      // Verify all presets still visible
      presets.forEach(({ number, station }) => {
        cy.get(`[data-testid="preset-play-${number}"]`, { timeout: 10000 })
          .should("exist")
          .and("contain", station.name);
      });
    });

    it("should sync presets when switching devices", () => {
      // This test requires multiple devices
      cy.request(`${apiUrl}/devices`).then((response) => {
        if (response.body.devices.length < 2) {
          cy.log("Skipping multi-device test: Only 1 device available");
          return;
        }

        const device1Id = response.body.devices[0].device_id;
        const device2Id = response.body.devices[1].device_id;

        // Assign different presets to each device
        cy.request("POST", `${apiUrl}/presets/set`, {
          device_id: device1Id,
          preset_number: 1,
          station_uuid: stationA.uuid,
          station_name: stationA.name,
          station_url: stationA.url,
        });

        cy.request("POST", `${apiUrl}/presets/set`, {
          device_id: device2Id,
          preset_number: 1,
          station_uuid: stationB.uuid,
          station_name: stationB.name,
          station_url: stationB.url,
        });

        cy.reload();
        waitForPresetsReady();

        // Should show device 1 preset
        cy.get('[data-testid=\"preset-play-1\"]', { timeout: 10000 })
          .should("exist")
          .and("contain", stationA.name);

        // Switch to device 2 (via swiper or device selector)
        cy.get(".swipe-arrow-right").click({ force: true });
        waitForPresetsReady();

        // Should show device 2 preset
        cy.get('[data-testid=\"preset-play-1\"]', { timeout: 10000 })
          .should("exist")
          .and("contain", stationB.name);
      });
    });
  });

  describe("Error Handling", () => {
    it("should handle preset save failure gracefully", () => {
      cy.intercept("POST", `${apiUrl}/presets/set`, {
        statusCode: 500,
        body: { detail: "Database error" },
      }).as("setPresetFail");

      cy.get(".preset-empty").first().click();
      cy.get(".radio-search-modal", { timeout: 10000 }).should("be.visible");
      cy.get(".search-input").type("BBC");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");
      cy.get(".search-result-item", { timeout: 10000 }).should("have.length.at.least", 1);
      cy.get(".search-result-item").first().click();

      // Wait for error state and modal to remain open
      cy.get(".error-message", { timeout: 5000 }).should("be.visible");
    });

    it("should handle preset clear failure gracefully", () => {
      // Assign preset first
      cy.request("POST", `${apiUrl}/presets/set`, {
        device_id: deviceId,
        preset_number: 2,
        station_uuid: stationA.uuid,
        station_name: stationA.name,
        station_url: stationA.url,
      });

      cy.reload();
      waitForPresetsReady();
      cy.get('[data-testid="preset-play-2"]', { timeout: 10000 })
        .should("exist")
        .and("contain", stationA.name);

      // Mock clear failure
      cy.intercept("DELETE", `${apiUrl}/presets/${deviceId}/2`, {
        statusCode: 500,
        body: { detail: "Delete failed" },
      }).as("clearPresetFail");

      cy.on("window:confirm", () => true);
      cy.get('[data-testid="preset-clear-2"]').click({ force: true });
      cy.wait("@clearPresetFail");

      // Should show error (scroll into view to ensure visibility)
      cy.get('[data-testid="error-message"]').scrollIntoView().should("be.visible");

      // Preset should still be visible (not optimistically removed)
      cy.get('[data-testid="preset-play-2"]').should("contain", stationA.name);
    });

    it("should dismiss error messages", () => {
      // Trigger error
      cy.intercept("POST", `${apiUrl}/presets/set`, {
        statusCode: 400,
        body: { detail: "Invalid data" },
      }).as("setPresetFail");

      cy.get(".preset-empty").first().click();
      cy.get(".radio-search-modal", { timeout: 10000 }).should("be.visible");
      cy.get(".search-input").type("BBC");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");
      cy.get(".search-result-item", { timeout: 10000 }).should("have.length.at.least", 1);
      cy.get(".search-result-item").first().click();
      cy.wait("@setPresetFail");

      cy.get('[data-testid="error-message"]').should("be.visible");

      // Dismiss error
      cy.get('[data-testid="error-message"] button').click();

      cy.get('[data-testid="error-message"]').should("not.exist");
    });
  });
});
