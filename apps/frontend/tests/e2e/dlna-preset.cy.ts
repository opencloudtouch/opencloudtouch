/**
 * E2E: DLNA in the preset dialog (mock mode).
 * Prerequisites: backend with OCT_MOCK_MODE=true (the fake "Mock Media Server": 120 tracks, nested folders).
 */
describe("DLNA in the preset dialog", () => {
  const apiUrl = Cypress.expose("apiUrl");
  let deviceId: string;

  beforeEach(() => {
    cy.window().then((win) => win.sessionStorage.clear());
    cy.request("DELETE", `${apiUrl}/devices`);
    cy.visit("/welcome");
    cy.get('[data-test="discover-button"]').click();
    cy.waitForDevices();
    cy.request(`${apiUrl}/devices`).then((response) => {
      deviceId = response.body.devices[0].device_id;
      cy.request("GET", `${apiUrl}/presets/${deviceId}`).then((presets) => {
        presets.body.forEach((p: { preset_number: number }) =>
          cy.request("DELETE", `${apiUrl}/presets/${deviceId}/${p.preset_number}`)
        );
      });
    });
  });

  const openDialog = () => {
    cy.visit("/");
    cy.get('[data-testid="preset-empty-1"]', { timeout: 15000 }).click();
    cy.get('[data-test="dlna-mode"]').click();
  };

  it("browses the mock server, loads more and puts a track on the preset button", () => {
    openDialog();
    cy.get(".dl-row--server button").click();

    // paging: the 120-entry folder offers "Load more" until has_more is false
    cy.contains(".dl-title", "Many Folders").click();
    cy.get(".dl-more button").click();
    cy.get(".dl-row").should("have.length.greaterThan", 50);

    cy.get(".dl-crumbs button").first().click(); // back to the server root
    cy.contains(".dl-title", "Music").click();
    cy.get(".dl-row--track .dl-slot").first().click();
    cy.get('[data-testid="preset-play-1"]').should("exist");
    cy.get('[data-testid="preset-1"] .pr-dlna').should("contain.text", "DLNA");
  });

  it("remembers the folder for the browser session", () => {
    openDialog();
    cy.get(".dl-row--server button").click();
    cy.get("button.dl-open").first().click();
    cy.get(".dl-crumb--current").should("exist");
    cy.get(".dlg-close").click();
    cy.get('[data-testid="preset-empty-1"]', { timeout: 15000 }).click();
    cy.get('[data-test="dlna-mode"]').click();
    cy.get(".dl-crumb--current").should("exist");
  });
});
