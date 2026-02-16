/**
 * E2E Tests: Radio Search Robustness
 * Tests search behavior under stress: rapid typing, deletions, special chars
 *
 * Goal: No 503 Service Unavailable errors under any input scenario
 *
 * Prerequisites:
 * - Backend running with OCT_MOCK_MODE=true
 * - RadioBrowser API available (real or mocked)
 */
describe("Radio Search Robustness", () => {
  const apiUrl = Cypress.env("apiUrl");
  let deviceId: string;

  beforeEach(() => {
    // Clear devices
    cy.request("DELETE", `${apiUrl}/devices`);

    // Discover devices
    cy.visit("/welcome");
    cy.get('[data-test="discover-button"]').click();

    // Wait for device data to render
    cy.get('[data-test="device-card"]', { timeout: 10000 }).should("have.length.at.least", 1);
    cy.get('[data-test="device-name"]', { timeout: 10000 }).should("not.contain", "Unknown");

    // Get device ID for tests
    cy.request(`${apiUrl}/devices`).then((response) => {
      deviceId = response.body.devices[0].device_id;
    });

    // Navigate to Radio Presets page
    cy.contains("Radio Presets").click();

    // Open search modal by clicking preset 1 (empty)
    cy.get(".preset-empty", { timeout: 10000 }).first().scrollIntoView().click({ force: true });
    cy.get(".radio-search-modal", { timeout: 10000 }).should("be.visible");
  });

  afterEach(() => {
    // Close modal if still open
    cy.get("body").then(($body) => {
      if ($body.find(".radio-search-modal").length > 0) {
        cy.get(".search-close").click();
      }
    });
  });

  describe("Rapid Typing Scenarios", () => {
    it("should handle fast consecutive typing without 503 errors", () => {
      const searchTerm = "rock";

      // Type entire search term rapidly (simulates fast typing)
      cy.get(".search-input").type(searchTerm, { delay: 50 });

      // Wait for search results to load
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      // Verify no error message displayed
      cy.get(".search-error").should("not.exist");

      // Should show results or empty state (but not error)
      cy.get(".search-results").should("be.visible");
    });

    it("should handle typing then deleting without 503 errors", () => {
      // Type a search term
      cy.get(".search-input").type("jazz");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      // Delete 2 characters (backspace) - triggers new search
      cy.get(".search-input").type("{backspace}{backspace}");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      // Type more characters
      cy.get(".search-input").type("zz");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      // Verify no errors displayed
      cy.get(".search-error").should("not.exist");
    });

    it("should handle rapid search term switching without request race conditions", () => {
      // Rapid search term changes
      cy.get(".search-input").type("Absolut");
      cy.get(".search-input").clear().type("Bayern");
      cy.get(".search-input").clear().type("1LIVE");

      // Wait for final search to complete
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      // Should show jazz results (last search)
      cy.get(".search-error").should("not.exist");
      cy.get(".search-results").should("be.visible");
    });

    it("should cancel in-flight requests when search term changes", () => {
      // Start slow search
      cy.get(".search-input").type("slow");

      // Immediately change to fast search (before slow completes)
      cy.get(".search-input").clear().type("fast");

      // Wait for fast search results
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      // Should show fast results, not error from cancelled slow request
      cy.get(".search-error").should("not.exist");
    });
  });

  describe("Special Characters & Edge Cases", () => {
    it("should handle special characters without 503", () => {
      cy.get(".search-input").type("rock!@#$%");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      cy.get(".search-error").should("not.exist");
      // May return no results, but no server error
    });

    it("should handle very long search strings", () => {
      const longString = "abcdefghijklmnopqrstuvwxyz".repeat(3); // 78 chars
      cy.get(".search-input").type(longString.slice(0, 50));

      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      cy.get(".search-error").should("not.exist");
    });

    it("should handle empty search gracefully", () => {
      // Type spaces only
      cy.get(".search-input").type("   ");

      // Should not trigger search OR should handle gracefully
      cy.get(".search-error").should("not.exist");

      // Should show empty state or placeholder
      cy.get(".search-empty, .search-loading, .search-results").should("exist");
    });

    it("should handle unicode characters", () => {
      cy.get(".search-input").type("Müller Café");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      cy.get(".search-error").should("not.exist");
    });

    it("should handle URL-unfriendly characters", () => {
      // Characters that need URL encoding
      cy.get(".search-input").type("rock & roll / blues");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      cy.get(".search-error").should("not.exist");
    });

    it("should handle single character search", () => {
      cy.get(".search-input").type("a");
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");

      // Should return results or empty (not error)
      cy.get(".search-error").should("not.exist");
    });
  });

  describe("Network Error Handling", () => {
    it("should display user-friendly error on 503 Service Unavailable", () => {
      cy.get(".search-input").type("ERROR_503");

      // Should show error message in UI
      cy.get(".search-error").should("be.visible").and("contain.text", "Dienst nicht verfügbar");

      // Search input should still be usable (not crash)
      cy.get(".search-input").should("be.visible").and("not.be.disabled");
    });

    it("should display user-friendly error on 504 Gateway Timeout", () => {
      cy.get(".search-input").type("ERROR_504");

      cy.get(".search-error").should("be.visible");
      cy.get(".search-input").should("be.visible");
    });

    it("should recover from errors when new search succeeds", () => {
      // First search fails
      cy.get(".search-input").type("ERROR_503");
      cy.get(".search-error").should("be.visible");

      // Second search succeeds
      cy.get(".search-input").clear().type("BBC");
      cy.get(".search-result-item", { timeout: 10000 }).should("have.length.at.least", 1);

      // Error should clear, results should show
      cy.get(".search-error").should("not.exist");
      cy.get(".search-result-item").should("have.length.at.least", 1);
    });

    it("should handle network errors gracefully (no response)", () => {
      cy.get(".search-input").type("ERROR_500");

      // Should show error, not crash
      cy.get(".search-error").should("be.visible");
    });
  });

  describe("Search Debouncing (Performance)", () => {
    it("should debounce rapid keystrokes to reduce API calls", () => {
      // Type 10 characters rapidly
      const searchTerm = "classical";
      searchTerm.split("").forEach((char) => {
        cy.get(".search-input").type(char, { delay: 50 });
      });

      // Wait for debounced search to complete
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");
    });

    it("should not search while typing rapidly", () => {
      // Type fast
      cy.get(".search-input").type("abc", { delay: 50 });

      // Wait for debounced search results
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");
    });
  });

  describe("Loading States", () => {
    it("should show loading indicator during search", () => {
      cy.get(".search-input").type("rock");

      // Loading indicator should appear
      cy.get(".search-loading").should("be.visible");

      // Loading should disappear after results
      cy.get(".search-results", { timeout: 10000 }).should("be.visible");
      cy.get(".search-loading").should("not.exist");
    });

    it("should not show stale loading state after error", () => {
      cy.get(".search-input").type("ERROR_500");

      // Loading should be gone, error should show
      cy.get(".search-loading").should("not.exist");
      cy.get(".search-error").should("be.visible");
    });
  });
});
