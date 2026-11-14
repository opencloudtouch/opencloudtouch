/**
 * UI audit: page x theme x viewport width. See cypress.ui-audit.config.ts.
 * Findings are collected and reported, they do not fail the run: the report is the result.
 */
import { collectLayoutIssues, waitForStableLayout } from "../support/layoutAudit";
import { collectContainmentIssues } from "../support/uiAudit/containment";
import { collectContrastIssues } from "../support/uiAudit/contrastDom";
import {
  screenshotName,
  shouldScreenshot,
  type AuditIssue,
  type AuditRecord,
} from "../support/uiAudit/report";

const DEVICE_ID = "A1B2C3D4E5F6";
const NOW = new Date().toISOString();
const DEVICES = [
  {
    device_id: DEVICE_ID,
    ip: "192.168.1.100",
    name: "Bose SoundTouch 30",
    model: "SoundTouch 30",
    firmware_version: "29.0.3.46291.53",
    mac_address: "A1:B2:C3:D4:E5:F6",
    last_seen: NOW,
  },
  {
    device_id: "B2C3D4E5F6A1",
    ip: "192.168.1.101",
    name: "Bose SoundTouch 10",
    model: "SoundTouch 10",
    firmware_version: "28.1.3.46291.53",
    mac_address: "B2:C3:D4:E5:F6:A1",
    last_seen: NOW,
  },
];
const PRESETS = [1, 2, 3].map((n) => ({
  id: n,
  device_id: DEVICE_ID,
  preset_number: n,
  station_uuid: `uuid-${n}`,
  station_name: `Station ${n}`,
  station_url: "http://example.invalid/stream.mp3",
  source: "LOCAL_INTERNET_RADIO",
  station_homepage: null,
  station_favicon: null,
  created_at: NOW,
  updated_at: NOW,
}));

interface AuditPage {
  path: string;
  devices: boolean;
  waitFor?: string;
}

const PAGES: AuditPage[] = [
  { path: "/", devices: true },
  { path: "/multiroom", devices: true },
  { path: "/settings", devices: true },
  { path: "/about", devices: true, waitFor: ".ab-cloud li" },
  { path: "/diagnostics", devices: true },
  { path: "/licenses", devices: true },
  { path: "/setup-wizard", devices: true },
  { path: "/welcome", devices: false },
  { path: "/does-not-exist", devices: true },
];
const THEMES = ["dark", "light"] as const;
const HEIGHT = 800;

function mockApi(devices: boolean) {
  cy.intercept("GET", "/api/devices", {
    body: devices ? { devices: DEVICES, count: DEVICES.length } : [],
  });
  cy.intercept("GET", `/api/presets/${DEVICE_ID}`, { body: devices ? PRESETS : [] });
  cy.intercept("GET", "/api/presets/*", { body: [] });
  cy.intercept("GET", "/api/stereo-pairs", { body: { pairs: [] } });
  cy.intercept("GET", "/api/settings/manual-ips", { body: [] });
  cy.intercept("GET", "/api/devices/discover/stream*", {
    statusCode: 200,
    body: "data: done\n\n",
    headers: { "Content-Type": "text/event-stream" },
  });
  cy.intercept("GET", "/api/devices/events*", {
    statusCode: 200,
    body: "",
    headers: { "Content-Type": "text/event-stream" },
  });
}

/** axe's own colour-contrast rule, as a second opinion next to our measurement. */
function axeContrast(): Cypress.Chainable<AuditIssue[]> {
  return cy.window({ log: false }).then(
    (win) =>
      new Cypress.Promise<AuditIssue[]>((resolve) => {
        const axe = (win as unknown as { axe: { run: Function } }).axe;
        axe
          .run(win.document, { runOnly: { type: "rule", values: ["color-contrast"] } })
          .then(
            (result: {
              violations: { nodes: { target: string[]; failureSummary?: string }[] }[];
            }) =>
              resolve(
                result.violations.flatMap((v) =>
                  v.nodes.map((n) => ({
                    kind: "axe-contrast",
                    selector: n.target.join(" "),
                    detail: (n.failureSummary ?? "").split("\n")[1]?.trim() ?? "color-contrast",
                  }))
                )
              )
          );
      })
  );
}

describe("UI audit", () => {
  let widths: number[] = [];
  let base: number[] = [];

  before(() => {
    cy.task("uiAudit:reset");
    cy.task("uiAudit:matrix").then((m) => {
      ({ widths, base } = m as { widths: number[]; base: number[] });
      cy.log(`${widths.length} widths: ${widths.join(", ")}`);
    });
  });

  after(() => {
    cy.task("uiAudit:report", {
      pages: PAGES.length,
      themes: THEMES.length,
      widths: widths.length,
    });
  });

  for (const page of PAGES) {
    for (const theme of THEMES) {
      it(`${page.path} (${theme})`, () => {
        mockApi(page.devices);
        cy.viewport(1280, HEIGHT);
        cy.visit(page.path, {
          onBeforeLoad: (win) => win.localStorage.setItem("oct-theme", theme),
        });
        cy.get("html").should("have.attr", "data-theme", theme);
        if (page.waitFor) cy.get(page.waitFor, { timeout: 8000 }).should("exist");
        cy.injectAxe();

        // Cypress queues the commands of this loop in order
        for (const width of widths) {
          cy.viewport(width, HEIGHT);
          cy.window({ log: false }).then((win) => waitForStableLayout(win));
          cy.window({ log: false }).then((win) => {
            const issues: AuditIssue[] = [
              ...collectLayoutIssues(win),
              ...collectContainmentIssues(win),
              ...collectContrastIssues(win),
            ];
            const withAxe = base.includes(width) ? axeContrast() : cy.wrap<AuditIssue[]>([]);
            withAxe.then((axeIssues) => {
              const all = [...issues, ...axeIssues];
              const record: AuditRecord = { page: page.path, theme, width, issues: all };
              cy.task("uiAudit:record", record, { log: false });
              if (shouldScreenshot(width, base, all.length > 0)) {
                cy.screenshot(screenshotName(page.path, theme, width).replace(/\.png$/, ""), {
                  capture: "viewport",
                  overwrite: true,
                  log: false,
                });
              }
            });
          });
        }
      });
    }
  }
});
