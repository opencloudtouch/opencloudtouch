/**
 * UI audit: page x theme x viewport width. See cypress.ui-audit.config.ts.
 * Findings are collected and reported, they do not fail the run: the report is the result.
 */
import { collectLayoutIssues, waitForStableLayout } from "../support/layoutAudit";
import { mockSetupWizardApi } from "../support/wizardMocks";
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

/** One audited screen: a route plus the API state and the interaction that leads to it. */
interface Scenario {
  /** shown in the report; page routes use their path, states add `~name` */
  id: string;
  path: string;
  mock: () => void;
  /** clicks that open the dialog / step, run after the page has loaded */
  act?: () => void;
  /** selector that proves the state is on screen */
  waitFor?: string;
}

const STEREO_BASE = {
  stereo_capable: true,
  oct_provisioned: true,
  stereo_ineligible_reason: null,
  stereo_pair_id: null,
  stereo_role: null,
  stereo_master: false,
  stereo_partner_name: null,
  stereo_master_name: null,
};
const stereoDevice = (n: number, name: string, firmware: string, extra = {}) => ({
  ...DEVICES[1],
  device_id: `C${n}C${n}C${n}C${n}C${n}C${n}`,
  ip: `192.168.1.${110 + n}`,
  name,
  firmware_version: firmware,
  ...STEREO_BASE,
  ...extra,
});
const STEREO_DEVICES = [
  stereoDevice(1, "Bose SoundTouch 10 A", "27.0.6"),
  stereoDevice(2, "Bose SoundTouch 10 B", "28.1.3"), // differs: firmware warning in step 2
  stereoDevice(3, "Bose SoundTouch 10 C", "27.0.6", {
    stereo_ineligible_reason: "in_pair",
    stereo_pair_id: 1,
    stereo_role: "LEFT",
    stereo_master: true,
    stereo_partner_name: "Bose SoundTouch 10 D",
  }),
  stereoDevice(4, "Bose SoundTouch 10 D", "27.0.6", { stereo_ineligible_reason: "not_provisioned" }),
];

const member = (id: string, name: string, role: "LEFT" | "RIGHT", reachable = true) => ({
  device_id: id,
  name,
  role,
  reachable,
});
const pair = (id: number, name: string, status: string, source: string, members: object[]) => ({
  id,
  name,
  status,
  source,
  members,
  warnings: [],
});
const PAIRS = [
  pair(1, "Wohnzimmer", "active", "device", [
    member("D1", "Bose SoundTouch 10 L", "LEFT"),
    member("D2", "Bose SoundTouch 10 R", "RIGHT"),
  ]),
  pair(2, "Küche", "degraded", "oct", [
    member("D3", "Bose SoundTouch 10 K1", "LEFT"),
    member("D4", "Bose SoundTouch 10 K2", "RIGHT", false),
  ]),
  pair(3, "Schlafzimmer", "active", "oct", [
    member("D5", "Bose SoundTouch 10 S1", "LEFT"),
    member("D6", "Bose SoundTouch 10 S2", "RIGHT", false),
  ]),
];

const STEPS = ["preflight", "create_left", "create_right", "verify"] as const;
const operation = (states: string[], extra: object) => ({
  state: "running",
  steps: STEPS.map((key, i) => ({ key, state: states[i] })),
  pair: null,
  warnings: [],
  error: null,
  ...extra,
});

/** Multi-room page with stereo-capable speakers and the given pair list / operation. */
function mockStereo(opts: { pairs?: unknown; pairsStatus?: number; delay?: number; op?: object }) {
  mockApi(true);
  cy.intercept("GET", "/api/devices", {
    body: { devices: STEREO_DEVICES, count: STEREO_DEVICES.length },
  });
  cy.intercept("GET", "/api/stereo-pairs", {
    statusCode: opts.pairsStatus ?? 200,
    body: opts.pairs ?? [],
    delay: opts.delay,
  });
  if (opts.op) {
    cy.intercept("POST", "/api/stereo-pairs", { body: { operation_id: "op-1" } });
    cy.intercept("GET", "/api/stereo-pairs/operations/op-1", { body: opts.op });
  }
}

/** Opens the create dialog and walks it to the given step (1 = pick, 2 = sides, 3 = run). */
function openCreateDialog(step: 1 | 2 | 3) {
  cy.get(".sp-create").should("not.be.disabled").click();
  cy.get("dialog[open] .mr-dev-check").should("exist");
  if (step === 1) return;
  cy.get("dialog[open] .mr-dev-check:not([disabled])").eq(0).check();
  cy.get("dialog[open] .mr-dev-check:not([disabled])").eq(1).check();
  cy.get("dialog[open] .dlg-actions .btn-primary").click();
  cy.get("dialog[open] .sp-slots").should("exist");
  if (step === 2) return;
  cy.get("dialog[open] .dlg-actions .btn-primary").click();
}

const page = (path: string, devices = true, waitFor?: string): Scenario => ({
  id: path,
  path,
  mock: () => mockApi(devices),
  waitFor,
});
const wizardStep = (query: string): Scenario => ({
  id: `/setup-wizard?${query}`,
  path: `/setup-wizard?${query}`,
  mock: () => {
    // anything a step asks for that is not mocked fails the same way every time
    cy.intercept("/api/**", { statusCode: 500, body: { detail: "not mocked in the UI audit" } });
    mockSetupWizardApi();
  },
  waitFor: "main",
});
const multiroom = (
  name: string,
  mock: () => void,
  act?: () => void,
  waitFor?: string
): Scenario => ({
  id: `/multiroom~${name}`,
  path: "/multiroom",
  mock,
  act,
  waitFor,
});

const SCENARIOS: Scenario[] = [
  page("/"),
  page("/multiroom"),
  page("/settings"),
  page("/about", true, ".ab-cloud li"),
  page("/diagnostics"),
  page("/licenses"),
  page("/setup-wizard"),
  page("/welcome", false),
  page("/does-not-exist"),
  multiroom(
    "zone-active",
    () => {
      mockStereo({});
      cy.intercept("GET", "/api/zones", {
        body: [
          {
            master_id: DEVICE_ID,
            master_ip: "192.168.1.100",
            is_master: true,
            members: [
              { device_id: DEVICE_ID, ip_address: "192.168.1.100", role: "master" },
              { device_id: "B2C3D4E5F6A1", ip_address: "192.168.1.101", role: "slave" },
            ],
          },
        ],
      });
    },
    undefined,
    ".zn-members"
  ),
  // stereo pairs on the multi-room page
  multiroom("pairs-empty", () => mockStereo({}), undefined, "[data-test='stereo-empty-ready']"),
  multiroom("pairs-list", () => mockStereo({ pairs: PAIRS }), undefined, "[data-test='stereo-pair']"),
  multiroom("pairs-loading", () => mockStereo({ delay: 600000 }), undefined, ".sp-skeleton"),
  multiroom(
    "pairs-error",
    () => mockStereo({ pairsStatus: 500, pairs: {} }),
    undefined,
    ".wz-status--error"
  ),
  // dialogs
  multiroom(
    "dissolve-confirm",
    () => mockStereo({ pairs: PAIRS.slice(0, 1) }),
    () => {
      cy.get("[data-test='stereo-pair'] .btn-danger-outline").first().click();
    },
    "[data-testid='confirm-dialog-confirm']"
  ),
  multiroom("create-step1", () => mockStereo({}), () => openCreateDialog(1)),
  multiroom("create-step2", () => mockStereo({}), () => openCreateDialog(2), ".sp-slots"),
  multiroom(
    "create-running",
    () => mockStereo({ op: operation(["done", "running", "waiting", "waiting"], {}) }),
    () => openCreateDialog(3),
    ".sp-op--running"
  ),
  multiroom(
    "create-succeeded",
    () =>
      mockStereo({
        op: operation(["done", "done", "done", "done"], { state: "succeeded", pair: PAIRS[0] }),
      }),
    () => openCreateDialog(3),
    "dialog .wz-status--success"
  ),
  multiroom(
    "create-failed",
    () =>
      mockStereo({
        op: operation(["done", "failed", "waiting", "waiting"], {
          state: "failed",
          error: { code: "stereo_pair_marge_failed", message: "failed" },
        }),
      }),
    () => openCreateDialog(3),
    "dialog .wz-status--error"
  ),
  multiroom(
    "create-degraded",
    () =>
      mockStereo({
        // the hook looks the left-over pair up by the left speaker the user picked
        pairs: [
          pair(2, "Küche", "degraded", "oct", [
            member(STEREO_DEVICES[0]?.device_id ?? "", "Bose SoundTouch 10 A", "LEFT"),
            member("D4", "Bose SoundTouch 10 B", "RIGHT", false),
          ]),
        ],
        op: operation(["done", "done", "failed", "waiting"], {
          state: "failed",
          error: { code: "stereo_pair_degraded", message: "failed" },
        }),
      }),
    () => openCreateDialog(3),
    "dialog .wz-status--warning"
  ),
  // setup wizard: every step of the setup flow, and the restore flow
  ...[2, 3, 4, 5, 6, 7, 8, 9].map((n) => wizardStep(`step=${n}`)),
  wizardStep("mode=restore"),
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
  // without this /multiroom stays in its zones error state and never shows the real page
  cy.intercept("GET", "/api/zones", { body: [] });
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
      pages: SCENARIOS.length,
      themes: THEMES.length,
      widths: widths.length,
    });
  });

  for (const scenario of SCENARIOS) {
    for (const theme of THEMES) {
      it(`${scenario.id} (${theme})`, () => {
        scenario.mock();
        cy.viewport(1280, HEIGHT);
        cy.visit(scenario.path, {
          onBeforeLoad: (win) => win.localStorage.setItem("oct-theme", theme),
        });
        cy.get("html").should("have.attr", "data-theme", theme);
        scenario.act?.();
        if (scenario.waitFor) cy.get(scenario.waitFor, { timeout: 8000 }).should("exist");
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
              const record: AuditRecord = { page: scenario.id, theme, width, issues: all };
              cy.task("uiAudit:record", record, { log: false });
              if (shouldScreenshot(width, base, all.length > 0)) {
                cy.screenshot(screenshotName(scenario.id, theme, width).replace(/\.png$/, ""), {
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
