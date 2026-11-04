/**
 * E2E: Stream recovery settings section on the Settings page.
 * Network is stubbed with cy.intercept (English UI).
 */

const DEFAULTS = {
  enabled: false,
  min_play_seconds: 600,
  max_attempts_per_hour: 3,
  updated_at: null,
};

const DEVICE = { device_id: "AABBCC112233", name: "Kitchen", ip: "192.168.1.100" };

function visitSettings() {
  cy.intercept("GET", "/api/devices", { body: { devices: [DEVICE], count: 1 } });
  cy.intercept("GET", "/api/settings/manual-ips", { body: { ips: [] } });
  cy.intercept("GET", "/api/devices/discover/stream*", {
    statusCode: 200,
    body: "data: done\n\n",
    headers: { "Content-Type": "text/event-stream" },
  });
  cy.visit("/settings", {
    onBeforeLoad(win) {
      win.localStorage.setItem("oct-lang", "en");
    },
  });
  cy.get("#stream-recovery").should("exist");
}

describe("Stream recovery settings", () => {
  it("shows the defaults and saves a changed configuration in seconds", () => {
    cy.intercept("GET", "/api/stream-recovery", { body: DEFAULTS });
    cy.intercept("PUT", "/api/stream-recovery", (req) => {
      req.reply({ body: { ...req.body, updated_at: "2026-10-26T06:00:00Z" } });
    }).as("save");
    visitSettings();

    cy.get("#stream-recovery").within(() => {
      cy.get('input[role="switch"]').should("not.be.checked");
      cy.get("#stream-recovery-minutes").should("have.value", "10").and("be.disabled");
      cy.get("#stream-recovery-attempts").should("have.value", "3").and("be.disabled");
      cy.contains("button", "Save").should("be.disabled");

      cy.get('input[role="switch"]').check();
      cy.get("#stream-recovery-minutes").clear().type("15");
      cy.contains("button", "Save").should("be.enabled").click();
    });

    cy.wait("@save").its("request.body").should("deep.equal", {
      enabled: true,
      min_play_seconds: 900,
      max_attempts_per_hour: 3,
    });
    cy.get("#stream-recovery").contains("button", "Save").should("be.disabled");
  });

  it("disables Save for out-of-range values", () => {
    cy.intercept("GET", "/api/stream-recovery", { body: DEFAULTS });
    visitSettings();

    cy.get("#stream-recovery").within(() => {
      cy.get('input[role="switch"]').check();
      cy.get("#stream-recovery-minutes").clear().type("1441");
      cy.contains("button", "Save").should("be.disabled");
      cy.get("#stream-recovery-minutes").should("have.attr", "aria-invalid", "true");
      cy.contains("Enter a whole number from 1 to 1440.").should("be.visible");

      cy.get("#stream-recovery-minutes").clear().type("20");
      cy.get("#stream-recovery-attempts").clear().type("11");
      cy.contains("button", "Save").should("be.disabled");
    });
  });

  it("shows the translated server error at the minutes input", () => {
    cy.intercept("GET", "/api/stream-recovery", { body: DEFAULTS });
    cy.intercept("PUT", "/api/stream-recovery", {
      statusCode: 422,
      body: {
        type: "validation_error",
        title: "Unprocessable Entity",
        status: 422,
        detail: "'min_play_seconds' must be an integer from 60 to 86400",
        code: "stream_recovery_min_play_invalid",
        errors: [
          {
            field: "body.min_play_seconds",
            path: "min_play_seconds",
            message: "raw backend text",
            code: "stream_recovery_min_play_invalid",
          },
        ],
      },
    });
    visitSettings();

    cy.get("#stream-recovery").within(() => {
      cy.get('input[role="switch"]').check();
      cy.get("#stream-recovery-minutes").clear().type("20");
      cy.contains("button", "Save").click();
      cy.contains("minimum playing time is out of range").should("be.visible");
      cy.contains("raw backend text").should("not.exist");
    });
  });

  it("loads the activity log only when expanded and offers Retry on errors", () => {
    cy.intercept("GET", "/api/stream-recovery", { body: DEFAULTS });
    let fail = true;
    cy.intercept("GET", "/api/stream-recovery/events*", (req) => {
      if (fail) {
        req.reply({ statusCode: 500, body: { detail: "x" } });
      } else {
        req.reply({
          body: {
            events: [
              {
                id: 1,
                occurred_at: "2026-10-26T05:52:08Z",
                device_id: DEVICE.device_id,
                preset_number: 2,
                station_name: "Radio X",
                play_seconds: 21600,
                outcome: "resumed",
                attempts: 1,
                error_code: null,
              },
            ],
          },
        });
      }
    }).as("events");
    visitSettings();

    cy.get("@events.all").should("have.length", 0);
    cy.get("#stream-recovery").within(() => {
      cy.contains("button", "Recent activity")
        .should("have.attr", "aria-expanded", "false")
        .click();
      cy.contains("button", "Recent activity").should("have.attr", "aria-expanded", "true");
      cy.contains("Could not load the activity.").should("be.visible");
      cy.then(() => {
        fail = false;
      });
      cy.contains("button", "Retry").click();
      cy.contains("td", "Resumed").should("be.visible");
      cy.contains("td", "Kitchen").should("be.visible");
      cy.contains("td", "6 h 0 min").should("be.visible");
    });
  });
});
