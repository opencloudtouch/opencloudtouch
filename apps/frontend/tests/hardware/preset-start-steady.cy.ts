/**
 * Real hardware: a preset start shows "starting" and then "playing" only, without idle or paused
 * in between (no flicker while the speaker buffers or restarts the track).
 *
 * Local only (cypress.hardware.config.ts, npm run test:hw); skips without CYPRESS_OCT_URL,
 * CYPRESS_HW_DEVICE_ID and CYPRESS_HW_PRESET. Sets the speaker volume to 1 first and pauses at the end.
 */
const octUrl = String(Cypress.expose("octUrl") ?? "").replace(/\/$/, "");
const deviceId = String(Cypress.expose("deviceId") ?? "");
const preset = Number(Cypress.expose("preset"));
const configured = !!octUrl && !!deviceId && preset >= 1 && preset <= 6;

const SAMPLE_MS = 200;
const OBSERVE_MS = 30000;
const ROW_STATES = ["playing", "paused", "starting", "failed", "saving"];

const api = (path: string) => `${octUrl}/api/devices/${encodeURIComponent(deviceId)}${path}`;
const rowState = (row: Element | null) =>
  ROW_STATES.find((s) => row?.classList.contains(`pr--${s}`)) ?? "idle";
const rowSelector = `[data-testid="preset-${preset}"]`;

(configured ? describe : describe.skip)("Preset start on real hardware", () => {
  before(() => {
    cy.request("PUT", api("/volume"), { level: 1 });
    cy.wait(1000);
    cy.request(api("/volume")).then(({ body }) => {
      if (body?.actual !== 1) {
        throw new Error(`Speaker volume reads ${body?.actual}, not 1: aborting before playback.`);
      }
    });
  });

  after(() => {
    cy.request("POST", api("/key?key=PAUSE&state=both"));
  });

  it("shows starting, then playing, and nothing else", () => {
    cy.visit(`/?device=${encodeURIComponent(deviceId)}`);
    cy.get(rowSelector, { timeout: 20000 }).should("exist");

    // A playing or paused row would toggle instead of start; switching the source for the
    // tester is not this test's call, so it stops and asks for another preset.
    cy.get(rowSelector).then((row) => {
      const state = rowState(row[0] ?? null);
      if (state !== "idle") {
        throw new Error(`Preset row is "${state}": choose a preset that is not the current one`);
      }
    });

    const samples: string[] = [];
    cy.window().then((win) => {
      cy.get(`[data-testid="preset-play-${preset}"]`)
        .scrollIntoView()
        .click()
        .then(() => {
          const read = () => samples.push(rowState(win.document.querySelector(rowSelector)));
          read();
          const timer = win.setInterval(read, SAMPLE_MS);
          cy.wait(OBSERVE_MS).then(() => win.clearInterval(timer));
        });
    });

    cy.then(() => {
      const seen = samples.filter((s, i) => s !== samples[i - 1]);
      cy.log(`row states: ${seen.join(" -> ")} (${samples.length} samples)`);
      expect(seen.join(" "), "observed row states").to.match(/^(starting )?playing$/);
    });
  });
});
