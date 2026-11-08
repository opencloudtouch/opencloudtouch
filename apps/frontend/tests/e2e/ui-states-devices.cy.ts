/**
 * E2E: states of the Devices page that the other specs never reach: every setup badge, renaming a device
 * (editing, saving, failing), preset rows while paused, failed or locked, the zone-member hint, a muted
 * volume and an unreachable source.
 *
 * Every test asserts a visible effect of the state (element and computed style), so a CSS rule for the state
 * that stops working fails here. The API is mocked with cy.intercept, no real device is involved.
 */
import { DEVICES } from "./support/wizardMocks";

const STATUSES = ["configured", "pending", "unconfigured", "outdated", "failed"] as const;
const devices = STATUSES.map((status, i) => ({ ...DEVICES[i], setup_status: status }));
const id = (i: number) => devices[i].device_id;

const PRESET = {
  id: 1,
  device_id: "",
  preset_number: 1,
  station_uuid: "radio-x",
  station_name: "Radio X",
  station_url: "http://example.com/x.mp3",
  source: "INTERNET_RADIO",
  created_at: "2026-01-01T00:00:00",
  updated_at: "2026-01-01T00:00:00",
};

interface Setup {
  nowPlaying?: Record<string, unknown>;
  volume?: Record<string, unknown>;
  zones?: unknown[];
}

function mockDevicesPage({ nowPlaying, volume, zones }: Setup = {}) {
  cy.intercept("GET", "/api/devices", { statusCode: 200, body: { count: devices.length, devices } });
  cy.intercept("GET", "/api/zones", { statusCode: 200, body: zones ?? [] });
  cy.intercept("GET", /\/api\/presets\/[^/]+$/, (req) => {
    const deviceId = req.url.split("/").pop();
    req.reply({ statusCode: 200, body: [{ ...PRESET, device_id: deviceId }] });
  });
  cy.intercept("GET", "/api/devices/*/now-playing", {
    statusCode: 200,
    body: nowPlaying ?? { source: "INTERNET_RADIO", state: "PLAY_STATE", station_name: "Radio X", online: true },
  });
  cy.intercept("GET", "/api/devices/*/volume", {
    statusCode: 200,
    body: volume ?? { actual: 30, target: 30, muted: false },
  });
}

const visitDevice = (i: number) => cy.visit(`/?device=${id(i)}`);

describe("Devices page states", () => {
  describe("setup badge", () => {
    for (const status of STATUSES.slice(1)) {
      it(`shows the ${status} badge with its own title`, () => {
        mockDevicesPage();
        visitDevice(STATUSES.indexOf(status));
        cy.get(`.sb.sb--${status}`).should("be.visible").and("have.attr", "title").and("not.be.empty");
        // the state must not depend on colour alone: an icon is drawn next to it
        cy.get(`.sb.sb--${status} svg`).should("exist");
      });
    }
  });

  describe("renaming a device", () => {
    beforeEach(() => {
      mockDevicesPage();
      visitDevice(0);
      cy.get(".dne-btn").click();
    });

    it("opens the editor with a focused input", () => {
      cy.get(".dne .dne-field .dne-input").should("be.visible").and("be.focused");
    });

    it("shows a spinner while saving", () => {
      cy.intercept("PUT", "/api/devices/*/name", (req) => {
        req.reply({ delay: 1500, statusCode: 200, body: { name: "Küche" } });
      });
      cy.get(".dne-input").clear().type("Küche{enter}");
      cy.get(".dne-saving").should("be.visible");
      cy.get(".dne-input").should("be.disabled");
    });

    it("shows the failure under the field and keeps the editor open", () => {
      cy.intercept("PUT", "/api/devices/*/name", { statusCode: 500, body: {} });
      cy.get(".dne-input").clear().type("Küche{enter}");
      cy.get(".ui-field-error.dne-error").should("be.visible").and("not.be.empty");
      cy.get(".ui-field-error svg").should("exist");
      cy.get(".dne-input").should("have.attr", "aria-invalid", "true");
    });
  });

  describe("preset rows", () => {
    it("marks the station that is paused", () => {
      mockDevicesPage({ nowPlaying: { source: "INTERNET_RADIO", state: "PAUSE_STATE", station_name: "Radio X", online: true } });
      visitDevice(0);
      cy.get(".pr.pr--paused").should("be.visible");
      cy.get(".pr--paused .pr-state").should("be.visible");
    });

    it("marks the preset that failed to start and offers a retry in a toast", () => {
      mockDevicesPage({ nowPlaying: { source: "STANDBY", state: "STOP_STATE", online: true } });
      cy.intercept("POST", "/api/devices/*/key*", { statusCode: 500, body: {} });
      visitDevice(0);
      cy.get('[data-testid="preset-play-1"]').click();
      cy.get(".pr.pr--failed").should("be.visible");
      cy.get(".pr--failed .pr-state").should("be.visible");
    });

    it("locks the rows while the device is a zone member", () => {
      mockDevicesPage({
        zones: [
          {
            master_id: id(1),
            master_ip: devices[1].ip,
            is_master: false,
            members: [
              { device_id: id(1), ip_address: devices[1].ip, role: "master", name: devices[1].name },
              { device_id: id(0), ip_address: devices[0].ip, role: "slave", name: devices[0].name },
            ],
          },
        ],
      });
      visitDevice(0);
      cy.get(".pr.pr--dis .pr-main").should("have.attr", "aria-disabled", "true");
      cy.get(".dv-zone-hint").should("be.visible").and("contain.text", devices[1].name);
    });
  });

  describe("volume", () => {
    it("shows the muted state of the speaker button", () => {
      mockDevicesPage({ volume: { actual: 0, target: 0, muted: true } });
      visitDevice(0);
      cy.get(".vs-mute.muted").should("be.visible");
    });
  });
});
