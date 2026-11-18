/**
 * E2E: a stereo pair is one device in the device list.
 *
 * The device list, now-playing and volume are mocked with cy.intercept, so the result does not depend on
 * the database or on real speakers. The pair is the LEFT (master) speaker; the RIGHT speaker is not shown.
 */
import { collectLayoutIssues, waitForStableLayout, waitForSettledAnimations } from "./support/layoutAudit";
import { DEVICES, visitDe } from "./support/wizardMocks";

const PAIR_ID = 7;
const PAIR_NAME = "Office Stereo";

const pairFields = (role: "LEFT" | "RIGHT") => ({
  stereo_capable: true,
  oct_provisioned: true,
  stereo_ineligible_reason: "in_pair",
  stereo_pair_id: PAIR_ID,
  stereo_role: role,
  stereo_master: role === "LEFT",
  stereo_partner_name: role === "LEFT" ? "Office right" : "Office left",
  stereo_master_name: "Office left",
  stereo_pair_name: PAIR_NAME,
});

const LEFT = { ...DEVICES[1]!, name: "Office left", model: "SoundTouch 10", ...pairFields("LEFT") };
const RIGHT = { ...DEVICES[2]!, name: "Office right", model: "SoundTouch 10", ...pairFields("RIGHT") };
const SINGLE = { ...DEVICES[0]!, name: "Kitchen" };

const asList = (devices: unknown[]) => ({ statusCode: 200, body: { count: devices.length, devices } });

describe("Stereo pair as one device", () => {
  let dissolved = false;

  beforeEach(() => {
    dissolved = false;
    cy.intercept("GET", "/api/devices", (req) => {
      const unpaired = [LEFT, RIGHT].map((d) => ({
        ...d,
        stereo_pair_id: null,
        stereo_role: null,
        stereo_master: false,
        stereo_partner_name: null,
        stereo_master_name: null,
        stereo_pair_name: null,
      }));
      req.reply(asList(dissolved ? [...unpaired, SINGLE] : [LEFT, RIGHT, SINGLE]));
    });
    cy.intercept("GET", "/api/devices/*/now-playing", {
      statusCode: 200,
      body: { source: "STANDBY", state: "STOP_STATE", online: true },
    });
    cy.intercept("GET", "/api/devices/*/volume", {
      statusCode: 200,
      body: { actual: 40, target: 40, muted: false },
    });
    cy.intercept("GET", "/api/zones", { statusCode: 200, body: [] });
    cy.intercept("GET", "/api/stereo-pairs", { statusCode: 200, body: [] });
  });

  it("shows one card for the pair with its name, the doubled model, the master ip and the badge", () => {
    visitDe(`/?device=${LEFT.device_id}`);

    cy.get(".ds-dot").should("have.length", 2); // the pair and the single speaker
    cy.get('[data-test="device-name"]').should("contain.text", PAIR_NAME);
    cy.get('[data-test="device-model"]').should("have.text", "2× SoundTouch 10");
    cy.get('[data-test="device-ip"]').should("have.text", LEFT.ip);
    cy.get('[data-test="device-stereo"]').should("have.text", "L/R Stereo");
    cy.get('[data-test="device-stereo-members"]').should("have.text", "Links: Office left · Rechts: Office right");
  });

  it("does not offer the right speaker as a device of its own", () => {
    visitDe(`/?device=${LEFT.device_id}`);

    cy.get(".ds-dot").should("have.length", 2);
    cy.get('[data-test="device-name"]').should("not.contain.text", "Office right");
  });

  it("keeps the source buttons usable, including AUX", () => {
    visitDe(`/?device=${LEFT.device_id}`);

    cy.get('.si-b button[aria-label="AUX"]').should("be.visible").and("not.have.attr", "aria-disabled", "true");
  });

  it("renames the pair from its card", () => {
    cy.intercept("PATCH", `/api/stereo-pairs/${PAIR_ID}`, {
      statusCode: 200,
      body: { id: PAIR_ID, name: "Studio Stereo", status: "active", source: "oct", members: [], warnings: [] },
    }).as("renamePair");
    visitDe(`/?device=${LEFT.device_id}`);

    cy.get('[data-test="device-name"]').click();
    cy.get(".rp-device-info input").clear().type("Studio Stereo{enter}");

    cy.wait("@renamePair").its("request.body").should("deep.equal", { name: "Studio Stereo" });
  });

  it("dissolves the pair after a confirmation and shows both speakers again", () => {
    cy.intercept("DELETE", `/api/stereo-pairs/${PAIR_ID}`, (req) => {
      dissolved = true;
      req.reply({ statusCode: 204 });
    }).as("dissolvePair");
    visitDe(`/?device=${LEFT.device_id}`);

    cy.get('[data-test="device-remove"]').scrollIntoView().should("contain.text", "Auflösen").click();
    cy.get("dialog.dlg[role='alertdialog']")
      .should("be.visible")
      .and("not.contain.text", "Preset")
      .and("contain.text", PAIR_NAME);
    cy.get('[data-testid="confirm-dialog-confirm"]').click();

    cy.wait("@dissolvePair");
    cy.get(".ds-dot").should("have.length", 3); // both speakers are single devices again
    cy.get('[data-test="device-name"]').should("contain.text", "Office left");
    cy.get('[data-test="device-stereo"]').should("not.exist");
  });

  it("keeps the pair when the dissolve is cancelled", () => {
    visitDe(`/?device=${LEFT.device_id}`);

    cy.get('[data-test="device-remove"]').scrollIntoView().click();
    cy.get('[data-testid="confirm-dialog-cancel"]').click();

    cy.get("dialog.dlg").should("not.exist");
    cy.get(".ds-dot").should("have.length", 2);
  });

  for (const width of [320, 375, 768, 1280]) {
    it(`has no layout issues and no accessibility violations @ ${width}px`, () => {
      cy.viewport(width, 800);
      visitDe(`/?device=${LEFT.device_id}`);
      cy.get('[data-test="device-stereo-members"]').should("be.visible");

      cy.window().then((win) => waitForStableLayout(win));
      cy.window().then((win) => {
        const issues = collectLayoutIssues(win);
        const text = issues.map((i) => `[${i.kind}] ${i.selector} (${i.detail})`).join(", ");
        expect(issues, `layout issues: ${text}`).to.have.lengthOf(0);
      });

      waitForSettledAnimations();
      cy.injectAxe();
      cy.checkA11y(undefined, { includedImpacts: ["critical", "serious", "moderate"] });
    });
  }
});
