/**
 * E2E: the Licenses page is reachable from the About page and keeps the selected device (#528).
 */
import { DEVICE, mockApi, visitDe } from "./support/wizardMocks";

describe("About: licenses link", { retries: 0 }, () => {
  beforeEach(() => {
    mockApi();
  });

  it("opens the licenses page from the About page", () => {
    visitDe("/about");
    cy.get('a[href^="/licenses"]').should("be.visible").click();
    cy.location("pathname").should("eq", "/licenses");
  });

  it("keeps the selected device in the link", () => {
    visitDe(`/about?device=${DEVICE.device_id}`);
    cy.get('a[href^="/licenses"]')
      .should("have.attr", "href", `/licenses?device=${encodeURIComponent(DEVICE.device_id)}`)
      .click();
    cy.location("pathname").should("eq", "/licenses");
    cy.location("search").should("eq", `?device=${encodeURIComponent(DEVICE.device_id)}`);
  });
});
