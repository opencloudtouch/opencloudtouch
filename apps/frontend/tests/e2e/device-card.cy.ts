/**
 * E2E: the device card on the Devices page (source switch, track keys, preset rows as toggles).
 *
 * The device list, now-playing, volume, presets and the device endpoints are mocked with cy.intercept, so the result
 * does not depend on the database or on real devices. Layout and axe of the card are covered by app-states.cy.ts.
 */
import { DEVICES, mockApi, visitDe } from "./support/wizardMocks";

const DEVICE = DEVICES[0]!;

const PRESETS = [
  { id: 1, device_id: DEVICE.device_id, preset_number: 1, station_uuid: "u1", station_name: "SWR3", station_url: "http://a.example/stream", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
  { id: 2, device_id: DEVICE.device_id, preset_number: 2, station_uuid: "u2", station_name: "NDR 2", station_url: "http://b.example/stream", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
];

function mockDeviceCard(nowPlaying: Record<string, unknown>) {
  mockApi();
  cy.intercept("GET", "/api/zones", { statusCode: 200, body: [] });
  cy.intercept("GET", "/api/devices/*/now-playing", { statusCode: 200, body: nowPlaying }).as("nowPlaying");
  cy.intercept("GET", "/api/devices/*/volume", { statusCode: 200, body: { actual: 40, target: 40, muted: false } });
  cy.intercept("GET", `/api/presets/${DEVICE.device_id}`, { statusCode: 200, body: PRESETS });
  cy.intercept("PUT", "/api/devices/*/source", { statusCode: 200, body: {} }).as("selectSource");
  cy.intercept("POST", "/api/devices/*/key*", { statusCode: 200, body: {} }).as("key");
}

describe("Device card", () => {
  beforeEach(() => {
    cy.viewport(390, 844);
  });

  it("is reached through the Devices navigation entry and has no Local control page", () => {
    mockDeviceCard({ source: "BLUETOOTH", state: "PLAY_STATE", station_name: "iPhone", track: "Song", artist: "Band" });
    visitDe(`/?device=${DEVICE.device_id}`);

    cy.contains("a.nav-link", "Geräte").should("have.attr", "aria-current", "page");
    cy.get("h1").should("contain", "Geräte");
    visitDe("/local");
    cy.get('[data-test="device-card"]').should("not.exist");
  });

  it("switches the source with the three buttons", () => {
    mockDeviceCard({ source: "INTERNET_RADIO", state: "PLAY_STATE", station_name: "SWR3" });
    visitDe(`/?device=${DEVICE.device_id}`);

    cy.get('[data-testid="source-presets"]').should("have.attr", "aria-pressed", "true");
    cy.get('[data-testid="source-bluetooth"]').click();
    cy.wait("@selectSource").its("request.body").should("deep.equal", { source: "BLUETOOTH" });
  });

  it("shows previous/next only for sources with tracks", () => {
    mockDeviceCard({ source: "BLUETOOTH", state: "PLAY_STATE", station_name: "iPhone", track: "Song", artist: "Band" });
    visitDe(`/?device=${DEVICE.device_id}`);

    cy.get('[data-test="dv-PREV_TRACK"]').should("be.visible");
    cy.get('[data-test="dv-NEXT_TRACK"]').click();
    cy.wait("@key").its("request.url").should("include", "key=NEXT_TRACK");
  });

  it("has no previous/next for radio", () => {
    mockDeviceCard({ source: "INTERNET_RADIO", state: "PLAY_STATE", station_name: "SWR3" });
    visitDe(`/?device=${DEVICE.device_id}`);

    cy.get('[data-test="dv-PLAY_PAUSE"]').should("be.visible");
    cy.get('[data-test="dv-PREV_TRACK"]').should("not.exist");
    cy.get('[data-test="dv-NEXT_TRACK"]').should("not.exist");
  });

  it("a preset row starts the preset when tapped; the pencil opens the station search", () => {
    mockDeviceCard({ source: "AUX", state: "PLAY_STATE" });
    visitDe(`/?device=${DEVICE.device_id}`);

    cy.get('[data-testid="preset-play-2"]').scrollIntoView().click();
    cy.wait("@key").its("request.url").should("include", "key=PRESET_2");

    cy.get('[data-testid="preset-change-2"]').click();
    cy.get("dialog[open]").should("exist");
  });

  it("a running preset is paused by tapping its row", () => {
    mockDeviceCard({ source: "INTERNET_RADIO", state: "PLAY_STATE", station_name: "NDR 2" });
    visitDe(`/?device=${DEVICE.device_id}`);

    cy.get('[data-testid="preset-play-2"]').scrollIntoView().should("have.attr", "aria-label").and("include", "pausieren");
    cy.get('[data-testid="preset-play-2"]').click();
    cy.wait("@key").its("request.url").should("include", "key=PLAY_PAUSE");
  });
});
