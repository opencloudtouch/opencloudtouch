/**
 * E2E: Sleep timer on the Local Control page.
 * Devices come from the mock backend (OCT_MOCK_MODE=true); only the sleep timer
 * endpoint is stubbed with cy.intercept so that no real minutes have to pass.
 */

const apiUrl = "http://localhost:7778/api";
const TIMER = /\/api\/devices\/[^/]+\/sleep-timer$/;

function status(endsInSeconds: number | null) {
  const now = Date.now();
  const iso = (ms: number) => new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
  if (endsInSeconds === null) return { active: false, server_time: iso(now) };
  return {
    active: true,
    server_time: iso(now),
    device_id: "AABBCC112233",
    ends_at: iso(now + endsInSeconds * 1000),
    duration_minutes: 30,
    fade_seconds: 30,
    end_action: "stop",
    state: "running",
  };
}

function visitLocalControl() {
  cy.visit("/local", {
    onBeforeLoad(win) {
      win.localStorage.setItem("oct-lang", "en");
    },
  });
  cy.get("#sleep-timer-title", { timeout: 15000 }).should("be.visible");
}

describe("Sleep timer", () => {
  beforeEach(() => {
    cy.request("DELETE", `${apiUrl}/devices`);
    cy.visit("/welcome", {
      onBeforeLoad(win) {
        win.localStorage.setItem("oct-lang", "en");
      },
    });
    cy.get('[data-test="discover-button"]').click();
    cy.get('[data-test="device-card"]', { timeout: 15000 }).should("have.length.at.least", 1);
  });

  it("starts a timer with the chosen values and shows the countdown", () => {
    let active = false;
    cy.intercept("GET", TIMER, (req) => req.reply(status(active ? 1800 : null)));
    cy.intercept("PUT", TIMER, (req) => {
      active = true;
      req.reply(status(1800));
    }).as("start");
    visitLocalControl();

    cy.get("#sleep-timer-fade").select("10");
    cy.get("#sleep-timer-end").select("standby");
    cy.contains("button", "Start timer").click();

    cy.wait("@start").its("request.body").should("deep.equal", {
      duration_minutes: 30,
      fade_seconds: 10,
      end_action: "standby",
    });
    cy.get('[role="timer"]').should("be.visible").and("contain.text", "29:");
  });

  it("cancels a running timer and returns to the start state", () => {
    let active = true;
    cy.intercept("GET", TIMER, (req) => req.reply(status(active ? 900 : null)));
    cy.intercept("DELETE", TIMER, (req) => {
      active = false;
      req.reply({ statusCode: 204 });
    }).as("cancel");
    visitLocalControl();

    cy.get('[role="timer"]').should("be.visible");
    cy.contains("button", "Cancel timer").click();
    cy.wait("@cancel");
    cy.contains("button", "Start timer").should("be.visible");
    cy.contains("Timer is no longer active").should("not.exist");
  });

  it("rejects a custom duration out of range without sending anything", () => {
    cy.intercept("GET", TIMER, (req) => req.reply(status(null)));
    cy.intercept("PUT", TIMER, cy.spy().as("put"));
    visitLocalControl();

    cy.get("#sleep-timer-duration").select("custom");
    cy.get("#sleep-timer-custom").clear().type("721");
    cy.contains("Enter a whole number from 1 to 720.").should("be.visible");
    cy.contains("button", "Start timer").should("be.disabled");
    cy.get("@put").should("not.have.been.called");
  });

  it("shows the translated server error at the fade control", () => {
    cy.intercept("GET", TIMER, (req) => req.reply(status(null)));
    cy.intercept("PUT", TIMER, {
      statusCode: 422,
      body: {
        type: "validation_error",
        title: "Unprocessable Entity",
        status: 422,
        detail: "fade too long",
        code: "sleep_timer_fade_too_long",
        errors: [
          {
            field: "fade_seconds",
            path: "fade_seconds",
            message: "raw backend text",
            code: "sleep_timer_fade_too_long",
          },
        ],
      },
    });
    visitLocalControl();

    cy.contains("button", "Start timer").click();
    cy.contains("The fade-out must not be longer than the timer.").should("be.visible");
    cy.contains("raw backend text").should("not.exist");
  });
});
