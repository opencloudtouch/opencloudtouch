/**
 * E2E: layout + accessibility of the interactive states of Local control, Zones and Firmware
 * (zone cards, device selection, selection bar, dissolve dialog, standby, playing).
 *
 * The device list, zones, now-playing and volume are mocked with cy.intercept, so the result does not depend on
 * the database or on real devices. Static page layout is covered by responsive.cy.ts.
 */
import { collectLayoutIssues, waitForStableLayout, LayoutIssue } from "./support/layoutAudit";
import { DEVICES, mockApi, visitDe } from "./support/wizardMocks";

const WIDTHS = [320, 375, 768, 1280];

const ZONE = {
  master_id: DEVICES[0]!.device_id,
  master_ip: DEVICES[0]!.ip,
  is_master: true,
  members: [
    { device_id: DEVICES[0]!.device_id, ip_address: DEVICES[0]!.ip, role: "master", name: DEVICES[0]!.name },
    { device_id: DEVICES[1]!.device_id, ip_address: DEVICES[1]!.ip, role: "slave", name: DEVICES[1]!.name },
    { device_id: DEVICES[2]!.device_id, ip_address: DEVICES[2]!.ip, role: "slave", name: DEVICES[2]!.name },
  ],
};

const PLAYING = {
  source: "INTERNET_RADIO",
  state: "PLAY_STATE",
  station_name: "Bayern 3 mit einem sehr langen Sendernamen ohne Leerzeichen_und_noch_mehr_Text",
  artist: "Eine Künstlerin mit einem außergewöhnlich langen Namen",
  track: "Ein ebenfalls sehr langer Titel der garantiert nicht in eine Zeile passt",
  artwork_url: "",
  online: true,
};
const STANDBY = { source: "STANDBY", state: "STOP_STATE", online: true };

type AxeViolation = { id: string; impact?: string | null; help: string; nodes: { target: unknown }[] };

function formatIssues(issues: LayoutIssue[]): string {
  return issues
    .map((i) => `[${i.kind}] ${i.selector}${i.other ? ` <-> ${i.other}` : ""} (${i.detail})`)
    .join("\n");
}

function assertNoLayoutIssues(label: string) {
  cy.window().then((win) => waitForStableLayout(win));
  cy.window().then((win) => {
    const issues = collectLayoutIssues(win);
    expect(issues.length, `${label}: layout issues\n${formatIssues(issues)}`).to.equal(0);
  });
}

function assertNoAxeViolations(label: string) {
  cy.wait(900); // let enter animations finish so contrast is measured on settled colours
  cy.injectAxe();
  let found: AxeViolation[] = [];
  cy.checkA11y(
    undefined,
    { includedImpacts: ["critical", "serious", "moderate"] },
    (violations) => {
      found = violations as unknown as AxeViolation[];
    },
    true,
  );
  cy.then(() => {
    const text = found
      .map((v) => `[${v.impact}] ${v.id}: ${v.help} (${v.nodes.length}x) -> ${v.nodes.slice(0, 3).map((n) => JSON.stringify(n.target)).join(", ")}`)
      .join("\n");
    expect(found.length, `axe violations on ${label}\n${text}`).to.equal(0);
  });
}

function mockPlayer(nowPlaying: Record<string, unknown>) {
  cy.intercept("GET", "/api/devices/*/now-playing", { statusCode: 200, body: nowPlaying });
  cy.intercept("GET", "/api/devices/*/volume", { statusCode: 200, body: { actual: 40, target: 40, muted: false } });
}

describe("Zones, Local control and Firmware states", { retries: 0 }, () => {
  beforeEach(() => {
    mockApi();
    mockPlayer(PLAYING);
    cy.intercept("GET", "/api/zones", { statusCode: 200, body: [ZONE] });
  });

  for (const width of WIDTHS) {
    describe(`@ ${width}px`, () => {
      beforeEach(() => {
        cy.viewport(width, 800);
      });

      it("zones: zone card, device selection and selection bar", () => {
        visitDe("/multiroom");
        cy.get(".zn").should("have.length", 1);
        // two devices that are not in the zone -> the selection bar appears
        cy.get(".mr-dev-check:not(:disabled)").eq(0).check({ force: true });
        cy.get(".mr-dev-check:not(:disabled)").eq(1).check({ force: true });
        cy.get(".mr-bar").should("exist");
        assertNoLayoutIssues(`multiroom selection @${width}`);
        assertNoAxeViolations(`multiroom selection @${width}`);
      });

      it("zones: the 'make master' star is a separate button and does not toggle the checkbox", () => {
        visitDe("/multiroom");
        cy.get(".mr-dev-check:not(:disabled)").eq(0).check({ force: true });
        cy.get(".mr-dev-check:not(:disabled)").eq(1).check({ force: true });
        cy.get(".mr-star").first().scrollIntoView().click();
        cy.get(".mr-dev-check:checked").should("have.length", 2);
      });

      it("zones: dissolve opens a confirmation dialog", () => {
        visitDe("/multiroom");
        cy.get(".zn .btn-danger-outline").first().scrollIntoView().click();
        cy.get("dialog.dlg[role='alertdialog']").should("be.visible");
        assertNoAxeViolations(`dissolve dialog @${width}`);
        cy.get('[data-testid="confirm-dialog-cancel"]').click();
        cy.get("dialog.dlg").should("not.exist");
      });

      it("local control: playing with a zone badge", () => {
        visitDe(`/local?device=${DEVICES[0]!.device_id}`);
        cy.get(".lc-zone", { timeout: 10000 }).should("exist");
        cy.get(".lc-key--primary").should("exist");
        assertNoLayoutIssues(`local playing @${width}`);
        assertNoAxeViolations(`local playing @${width}`);
      });

      it("local control: standby", () => {
        mockPlayer(STANDBY);
        visitDe(`/local?device=${DEVICES[3]!.device_id}`);
        cy.get(".lc-power--off", { timeout: 10000 }).should("exist");
        assertNoLayoutIssues(`local standby @${width}`);
        assertNoAxeViolations(`local standby @${width}`);
      });

      it("firmware: axe", () => {
        visitDe("/firmware");
        cy.get(".fw-item").should("have.length.at.least", 1);
        assertNoAxeViolations(`firmware @${width}`);
      });
    });
  }
});
