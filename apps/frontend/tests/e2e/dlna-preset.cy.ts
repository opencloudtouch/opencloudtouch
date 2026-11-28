/**
 * E2E: DLNA tab in the preset dialog (mock mode).
 * Prerequisites: backend with OCT_MOCK_MODE=true. Its in-process "Mock Media Server" reaches READY
 * once set up and serves Albums > Album One/Two, Photos (image first) and Single Track.
 */
describe("DLNA in the preset dialog", () => {
  const apiUrl = Cypress.expose("apiUrl");
  const SERVER_ID = "4d696e69-0000-0000-0000-00000000c0de";
  let deviceId: string;

  beforeEach(() => {
    // Selectors use English labels; the browser locale must not decide the UI language.
    cy.on("window:before:load", (win) => win.localStorage.setItem("oct-lang", "en"));
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

  const openDialog = (slot: number) => {
    cy.visit("/");
    cy.get(`[data-testid="preset-empty-${slot}"]`, { timeout: 15000 }).click();
    cy.get('[data-test="dlna-mode"]').click();
  };

  /** Sets the mock server up when needed (state lives in the backend process) and opens it. */
  const openServer = () => {
    cy.get(".dsl-row", { timeout: 15000 }).should("exist");
    cy.get("body").then(($body) => {
      if ($body.find('.dsl-row[data-state="not_enabled"]').length) {
        cy.get('button[aria-label="Set up Mock Media Server"]').click();
      }
    });
    cy.get('button[aria-label="Open Mock Media Server"]', { timeout: 15000 }).click();
    cy.get(".dlb-list").should("exist");
  };

  const openFolder = (title: string) => cy.get(`button[aria-label="Open folder ${title}"]`).click();
  const select = (title: string) => cy.get(`button[aria-label="Select ${title}"]`).click();

  const saveAlbumOneToSlot3 = () => {
    openDialog(3);
    openServer();
    openFolder("Albums");
    select("Album One");
    cy.get('[data-testid="preset-play-3"]', { timeout: 15000 }).should("exist");
  };

  it("sets up the mock server, which reaches READY", () => {
    openDialog(1);
    openServer();
    cy.request(`${apiUrl}/dlna/native?device_id=${deviceId}`)
      .its("body.servers")
      .then((servers: Array<{ server_id: string; state: string }>) => {
        expect(servers.find((s) => s.server_id === SERVER_ID)?.state).to.eq("ready");
      });
  });

  it("saves an album folder to slot 3 and shows the DLNA badge", () => {
    saveAlbumOneToSlot3();
    cy.get('[data-testid="preset-3"]').should("contain.text", "Album One");
    cy.get('[data-testid="preset-3"] .pb-dlna').should("contain.text", "DLNA");
  });

  it("warns before saving a folder whose first item is an image", () => {
    openDialog(2);
    openServer();
    select("Photos");
    cy.get('.dlp [role="alert"]').should("contain.text", "Save anyway");
    cy.contains("button", "Save anyway").click();
    cy.get('[data-testid="preset-play-2"]', { timeout: 15000 }).should("exist");
  });

  it("opens the edit dialog at the parent folder and deletes the preset", () => {
    saveAlbumOneToSlot3();
    cy.get('[data-testid="preset-change-3"]').click();
    cy.get('.dlb-crumbs [aria-current="location"]', { timeout: 15000 }).should(
      "contain.text",
      "Albums"
    );
    cy.get('button[aria-label="Select Album One"]').should("exist");

    cy.get('button[aria-label="Delete preset"]').click();
    cy.get('[data-testid="confirm-dialog-confirm"]').click();
    cy.get('[data-testid="preset-empty-3"]', { timeout: 15000 }).should("exist");
  });

  it("lists the affected slots before removing a server and removes it anyway", () => {
    saveAlbumOneToSlot3();
    // Show the registered server as not found, the only case with a remove button (decision 32).
    cy.intercept("GET", "**/api/dlna/native*", (request) => {
      request.continue((response) => {
        response.body.servers = response.body.servers.map((s: object) => ({
          ...s,
          discovered: false,
        }));
      });
    });
    cy.intercept("DELETE", "**/api/dlna/native/*/servers/*?force=true").as("forceRemove");

    cy.get('[data-testid="preset-change-3"]').click();
    cy.get('button[aria-label="All media servers"]', { timeout: 15000 }).click();
    cy.get('button[aria-label="Remove Mock Media Server"]', { timeout: 15000 }).click();
    cy.get('[data-testid="confirm-dialog-confirm"]').click();
    cy.contains("Presets on slots 3 still play from this server").should("be.visible");
    cy.get('[data-testid="confirm-dialog-confirm"]').should("have.text", "Remove anyway").click();
    cy.wait("@forceRemove").its("response.statusCode").should("eq", 204);
    cy.get('[data-testid="confirm-dialog-confirm"]').should("not.exist");
    // Presets stay saved (decision 29).
    cy.get('[data-testid="preset-3"]').should("contain.text", "Album One");
  });

  it("shows a source_error from the SSE stream and hides it on dismiss", () => {
    // The stream reconnects every 500 ms; the event is sent once, after the page has subscribed.
    let send = false;
    cy.intercept("GET", "**/api/events/device-stream*", (request) => {
      const event = send
        ? `event: source_error
data: {"device_id":"${deviceId}","code":1608}

`
        : "";
      send = false;
      request.reply({
        headers: { "Content-Type": "text/event-stream" },
        body: `retry: 500
${event}`,
      });
    });
    cy.visit("/");
    cy.get('[data-testid="preset-1"]', { timeout: 15000 }).then(() => {
      send = true;
    });
    cy.get('[data-testid="source-error"]', { timeout: 15000 })
      .should("be.visible")
      .and("contain.text", "Media server not found");
    cy.get('[data-testid="source-error"] .ui-alert-close').click();
    cy.get('[data-testid="source-error"]').should("not.exist");
  });

  it("shows a preset list pushed by the SSE presets event without a reload", () => {
    const preset = {
      id: 2,
      device_id: deviceId,
      preset_number: 2,
      station_uuid: "pushed-2",
      station_name: "Pushed Station",
      station_url: "http://stream.example/pushed",
      source: "TUNEIN",
      dlna: false,
      created_at: "2026-01-01T00:00:00",
      updated_at: "2026-01-01T00:00:00",
    };
    let send = false;
    cy.intercept("GET", "**/api/events/device-stream*", (request) => {
      const event = send
        ? `event: presets
data: ${JSON.stringify({ device_id: deviceId, presets: [preset] })}

`
        : "";
      send = false;
      request.reply({
        headers: { "Content-Type": "text/event-stream" },
        body: `retry: 500
${event}`,
      });
    });
    cy.visit("/");
    cy.get('[data-testid="preset-1"]', { timeout: 15000 }).then(() => {
      send = true;
    });
    cy.get('[data-testid="preset-2"]', { timeout: 15000 }).should("contain.text", "Pushed Station");
  });

  it("reaches every DLNA dialog control by focus and completes the flow", () => {
    // Cypress cannot synthesize the native Enter-to-click default action, so each control must be a
    // focusable native button that is then activated.
    const focusAndActivate = (selector: string) => {
      cy.get(selector, { timeout: 15000 }).first().focus().should("have.focus").click();
    };
    openDialog(4);
    cy.get(".dsl-row", { timeout: 15000 }).should("exist");
    cy.get("body").then(($body) => {
      if ($body.find('.dsl-row[data-state="not_enabled"]').length) {
        focusAndActivate('button[aria-label="Set up Mock Media Server"]');
      }
    });
    focusAndActivate('button[aria-label="Open Mock Media Server"]');
    focusAndActivate('button[aria-label="Open folder Albums"]');
    focusAndActivate('button[aria-label="Select Album Two"]');
    cy.get('[data-testid="preset-play-4"]', { timeout: 15000 }).should("exist");
  });
});
