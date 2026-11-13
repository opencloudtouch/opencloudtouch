/**
 * E2E: states of the app shell, About, Diagnostics and Settings that the other specs never reach: the slow-start
 * hints, an available update, a diagnostics page without devices and a failed log download.
 *
 * Every test asserts a visible effect of the state. The API is mocked with cy.intercept, no real device is involved.
 */
import { DEVICES } from "./support/wizardMocks";

describe("Page states", () => {
  it("shows a hint and then a retry button while the device list loads slowly", () => {
    cy.intercept("GET", "/api/devices", (req) => {
      req.reply({ delay: 15000, statusCode: 200, body: { count: 0, devices: [] } });
    });
    cy.visit("/");
    cy.get(".app-state-hint", { timeout: 8000 }).should("be.visible");
    cy.contains(".app-state .btn", /./, { timeout: 12000 }).should("be.visible");
  });

  describe("Welcome", () => {
    const sse = (data: object) => ({
      statusCode: 200,
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
      body: `event: error
data: ${JSON.stringify(data)}

`,
    });

    it("answers a scan that is already running with an info hint, not an error", () => {
      cy.intercept("GET", "/api/devices", { statusCode: 200, body: { count: 0, devices: [] } });
      cy.intercept(
        "GET",
        "/api/devices/discover/stream*",
        sse({ message: "Discovery already in progress", code: "discovery_in_progress" })
      );
      cy.visit("/welcome");
      cy.get('[data-test="discover-button"]').click();
      cy.get(".toast-info").should("be.visible");
      cy.get(".toast-error").should("not.exist");
    });

    it("reports any other scan failure as an error", () => {
      cy.intercept("GET", "/api/devices", { statusCode: 200, body: { count: 0, devices: [] } });
      cy.intercept(
        "GET",
        "/api/devices/discover/stream*",
        sse({ message: "Backend discovery process crashed" })
      );
      cy.visit("/welcome");
      cy.get('[data-test="discover-button"]').click();
      cy.get(".toast-error").should("be.visible");
      cy.get(".toast-info").should("not.exist");
    });
  });

  describe("About", () => {
    beforeEach(() => {
      cy.intercept("GET", "/api/devices", {
        statusCode: 200,
        body: { count: 1, devices: [DEVICES[0]] },
      });
    });

    it("announces a newer release with a link to it", () => {
      cy.intercept("GET", "/health", {
        statusCode: 200,
        body: { status: "healthy", version: "1.0.0", build: "official", uptime: 120 },
      });
      cy.intercept("GET", "https://api.github.com/repos/**", {
        statusCode: 200,
        body: {
          tag_name: "v9.9.9",
          html_url: "https://github.com/scheilch/opencloudtouch/releases/tag/v9.9.9",
        },
      });
      cy.visit("/about");
      cy.get(".ab-update .ab-update-body", { timeout: 10000 }).should("be.visible");
      cy.get(".ab-update .btn.btn-sm")
        .should("be.visible")
        .and("have.attr", "href")
        .and("include", "v9.9.9");
      cy.get(".btn .ab-ext").should("exist");
      cy.get(".ab-build-time").should("be.visible");
    });
  });

  describe("Diagnostics", () => {
    it("shows an explanation instead of an empty device list", () => {
      cy.intercept("GET", "/api/devices", {
        statusCode: 200,
        body: { count: 1, devices: [DEVICES[0]] },
      });
      cy.intercept("GET", "/api/diagnostics", {
        statusCode: 200,
        body: {
          server: {
            version: "1.0.0",
            python_version: "3.11",
            platform: "test",
            discovery_enabled: true,
            mock_mode: false,
            log_level: "INFO",
            manual_device_ips: 0,
            timestamp: "2026-01-01T00:00:00",
          },
          devices: [],
          db_stats: { devices: 0, presets: 0 },
        },
      });
      cy.visit("/diagnostics");
      cy.get(".dg-empty").should("be.visible").and("not.be.empty");
      cy.get(".dg-empty svg").should("exist");
    });

    it("marks the download button as busy and disabled while the report is built", () => {
      cy.intercept("GET", "/api/devices", {
        statusCode: 200,
        body: { count: 1, devices: [DEVICES[0]] },
      });
      cy.intercept("POST", "/api/bug-report/diagnostics", (req) => {
        req.reply({ delay: 2000, statusCode: 500, body: {} });
      });
      cy.visit("/diagnostics");
      cy.get(".dg-download-btn").click();
      cy.get(".dg-download-btn").should("have.attr", "aria-disabled", "true");
    });
  });

  describe("Settings", () => {
    it("shows why the log download failed", () => {
      cy.intercept("GET", "/api/devices", {
        statusCode: 200,
        body: { count: 1, devices: [DEVICES[0]] },
      });
      cy.intercept("POST", "/api/logs/backend", { statusCode: 500, body: {} });
      cy.visit("/settings");
      cy.get(".st-download-btn").click();
      cy.get(".st-download-error").should("be.visible").and("not.be.empty");
    });
  });
});
