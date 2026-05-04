/**
 * E2E Tests: Device Offline Display
 * Regression test for #82: UI must show clear offline indicator when device is unreachable.
 *
 * Strategy: Uses cy.intercept to simulate 503 responses from backend
 * for device-specific endpoints (now-playing, volume) while keeping
 * the device list itself reachable.
 *
 * Prerequisites:
 * - Backend running with OCT_MOCK_MODE=true on port 7778
 * - Frontend running on port 4173
 */

/** Force German locale — CI defaults to English (navigator.language='en') */
function visitDe(url: string, options?: Partial<Cypress.VisitOptions>) {
  cy.visit(url, {
    ...options,
    onBeforeLoad(win) {
      win.localStorage.setItem("oct-lang", "de");
      options?.onBeforeLoad?.(win);
    },
  });
}

describe("Device Offline Display", () => {
  const apiUrl = "http://localhost:7778/api";

  beforeEach(() => {
    // Clear DB and discover devices (normal path)
    cy.request("DELETE", `${apiUrl}/devices`);
    visitDe("/welcome");
    cy.get('[data-test="discover-button"]').click();
    cy.waitForDevices();

    // Should redirect to dashboard with devices loaded
    cy.url().should("eq", Cypress.config().baseUrl + "/");
    cy.get('[data-test="device-card"]', { timeout: 10000 }).should("have.length.at.least", 1);
  });

  describe("Offline Banner Appearance", () => {
    it("should show offline banner when now-playing returns 503", () => {
      // Intercept now-playing and volume to return 503 (device offline)
      cy.intercept("GET", "/api/devices/*/now-playing", {
        statusCode: 503,
        body: {
          type: "service_unavailable",
          title: "Device Unavailable",
          status: 503,
          detail: "Failed to connect to device",
        },
      }).as("nowPlaying503");

      cy.intercept("GET", "/api/devices/*/volume", {
        statusCode: 503,
        body: {
          type: "service_unavailable",
          title: "Device Unavailable",
          status: 503,
          detail: "Failed to connect to device",
        },
      }).as("volume503");

      // Wait for the 503 response to be processed
      cy.wait("@nowPlaying503");

      // Offline banner should appear
      cy.get('[data-testid="device-offline-banner"]', { timeout: 10000 })
        .should("be.visible")
        .and("contain.text", "Gerät nicht erreichbar");
    });

    it("should show device name in offline banner", () => {
      cy.intercept("GET", "/api/devices/*/now-playing", {
        statusCode: 503,
        body: {
          type: "service_unavailable",
          title: "Device Unavailable",
          status: 503,
          detail: "Failed to connect",
        },
      }).as("nowPlaying503");

      cy.intercept("GET", "/api/devices/*/volume", {
        statusCode: 503,
        body: {
          type: "service_unavailable",
          title: "Device Unavailable",
          status: 503,
          detail: "Failed to connect",
        },
      }).as("volume503");

      // Reload so intercepts are active on initial mount (avoids polling-cycle race condition)
      cy.reload();
      cy.wait("@nowPlaying503", { timeout: 10000 });

      // Banner should include device name (from the device card header)
      cy.get('[data-testid="device-offline-banner"]', { timeout: 10000 })
        .should("be.visible")
        .find(".offline-detail")
        .should("contain.text", "ist offline oder nicht im Netzwerk");
    });

    it("should have role=alert for accessibility", () => {
      cy.intercept("GET", "/api/devices/*/now-playing", {
        statusCode: 503,
        body: {
          type: "service_unavailable",
          title: "Device Unavailable",
          status: 503,
          detail: "Failed to connect",
        },
      }).as("nowPlaying503");

      cy.intercept("GET", "/api/devices/*/volume", { statusCode: 503 }).as("volume503");

      cy.wait("@nowPlaying503");

      cy.get('[role="alert"]', { timeout: 10000 })
        .should("be.visible")
        .and("have.attr", "data-testid", "device-offline-banner");
    });
  });

  describe("Controls Hidden When Offline", () => {
    // Tests in this block navigate to /local (LocalControl) because volume-section,
    // source-section, and playback-section only exist there.
    // Intercepts are registered BEFORE cy.visit so the very first mount request hits them.

    it("should hide volume, source, and playback controls when device is offline", () => {
      cy.intercept("GET", "/api/devices/*/now-playing", { statusCode: 503 }).as("nowPlaying503");
      cy.intercept("GET", "/api/devices/*/volume", { statusCode: 503 }).as("volume503");

      visitDe("/local");
      cy.wait("@nowPlaying503", { timeout: 10000 });

      cy.get('[data-testid="device-offline-banner"]', { timeout: 10000 }).should("be.visible");

      // Controls should NOT be visible when device is offline
      cy.get(".volume-section").should("not.exist");
      cy.get(".source-section").should("not.exist");
      cy.get(".playback-section").should("not.exist");
    });

    it("should keep device header visible when offline", () => {
      cy.intercept("GET", "/api/devices/*/now-playing", { statusCode: 503 }).as("nowPlaying503");
      cy.intercept("GET", "/api/devices/*/volume", { statusCode: 503 }).as("volume503");

      visitDe("/local");
      cy.wait("@nowPlaying503", { timeout: 10000 });

      cy.get('[data-testid="device-offline-banner"]', { timeout: 10000 }).should("be.visible");

      // Device header (name, power button) must remain visible even when offline
      cy.get(".control-card-header").should("be.visible");
      cy.get(".device-name").should("be.visible");
    });
  });

  describe("Recovery: Device Comes Back Online", () => {
    it("should remove offline banner and restore controls when device recovers", () => {
      // Phase 1: offline — intercept registered BEFORE visit so initial mount request gets 503
      cy.intercept("GET", "/api/devices/*/now-playing", { statusCode: 503 }).as("nowPlaying503");
      cy.intercept("GET", "/api/devices/*/volume", { statusCode: 503 }).as("volume503");

      visitDe("/local");
      cy.wait("@nowPlaying503", { timeout: 10000 });

      cy.get('[data-testid="device-offline-banner"]', { timeout: 10000 }).should("be.visible");
      cy.get(".volume-section").should("not.exist");

      // Phase 2: recovery — override intercepts to return 200 (device back online), then reload.
      // cy.reload() resets the JS module context, so offlineDeviceStore clears.
      // Using explicit 200 responses (not req.continue()) so the test does not depend on
      // the mock backend returning success for device-specific endpoints.
      cy.intercept("GET", "/api/devices/*/now-playing", {
        statusCode: 200,
        body: { source: "STANDBY", status: null },
      }).as("nowPlayingOnline");
      cy.intercept("GET", "/api/devices/*/volume", {
        statusCode: 200,
        body: { actual_volume: 30, muted: false },
      }).as("volumeOnline");
      cy.reload();

      cy.get(".volume-section", { timeout: 15000 }).should("be.visible");
      cy.get('[data-testid="device-offline-banner"]').should("not.exist");
    });
  });
});
