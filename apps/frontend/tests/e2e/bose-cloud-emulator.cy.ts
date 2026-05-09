/**
 * E2E Tests: Bose Cloud Emulator
 *
 * Tests the three cloud emulation domains (marge, bmx, swupdate)
 * that replace Bose's real cloud services for offline SoundTouch operation.
 *
 * Prerequisites:
 * - Backend running with OCT_MOCK_MODE=true on port 7778
 *
 * Endpoints tested:
 *   marge (streaming.bose.com):
 *     GET /v1/systems/devices/{id}          → Account sync XML
 *     GET /v1/systems/devices/{id}/presets  → Preset list XML
 *     GET /v1/systems/devices/{id}/sources  → Source list XML
 *     GET /v1/systems/devices/{id}/recents  → Recent plays XML
 *
 *   bmx (content.api.bose.io):
 *     GET /bmx/registry/v1/services         → Service registry JSON
 *     GET /bmx/tunein/v1/playback/station/{id} → TuneIn stream resolve
 *
 *   swupdate (worldwide.bose.com):
 *     GET /updates/soundtouch               → Firmware INDEX.XML
 *     GET /ced/eup/downloads/rel/{file}     → Firmware download (blocked)
 */
describe("Bose Cloud Emulator", () => {
  const BACKEND = "http://localhost:7778";
  const TEST_DEVICE_ID = "MOCK_DEVICE_001";

  // ─── Marge (streaming.bose.com) ───────────────────────────────────────────

  describe("Marge — Account Sync", () => {
    it("should return account XML for any device ID", () => {
      cy.request({
        url: `${BACKEND}/v1/systems/devices/${TEST_DEVICE_ID}`,
        headers: { Accept: "application/xml" },
      }).then((resp) => {
        expect(resp.status).to.eq(200);
        expect(resp.headers["content-type"]).to.include("xml");
      });
    });

    it("should return preset list XML", () => {
      cy.request({
        url: `${BACKEND}/v1/systems/devices/${TEST_DEVICE_ID}/presets`,
        headers: { Accept: "application/xml" },
      }).then((resp) => {
        expect(resp.status).to.eq(200);
        expect(resp.body).to.include("<presets");
      });
    });

    it("should return source list XML", () => {
      cy.request({
        url: `${BACKEND}/v1/systems/devices/${TEST_DEVICE_ID}/sources`,
        headers: { Accept: "application/xml" },
      }).then((resp) => {
        expect(resp.status).to.eq(200);
        expect(resp.body).to.include("<sources");
      });
    });

    it("should return recents XML", () => {
      cy.request({
        url: `${BACKEND}/v1/systems/devices/${TEST_DEVICE_ID}/recents`,
        headers: { Accept: "application/xml" },
      }).then((resp) => {
        expect(resp.status).to.eq(200);
        expect(resp.body).to.include("<recents");
      });
    });
  });

  // ─── BMX (content.api.bose.io) ────────────────────────────────────────────

  describe("BMX — Service Registry", () => {
    it("should return service registry with TUNEIN", () => {
      cy.request(`${BACKEND}/bmx/registry/v1/services`).then((resp) => {
        expect(resp.status).to.eq(200);
        const body =
          typeof resp.body === "string" ? JSON.parse(resp.body) : resp.body;
        const services = body.bmx_services || [];
        const tuneIn = services.find(
          (s: { id: { name: string } }) => s.id.name === "TUNEIN"
        );
        expect(tuneIn).to.not.be.undefined;
      });
    });

    it("should return RADIOBROWSER service", () => {
      cy.request(`${BACKEND}/bmx/registry/v1/services`).then((resp) => {
        const body =
          typeof resp.body === "string" ? JSON.parse(resp.body) : resp.body;
        const services = body.bmx_services || [];
        const rb = services.find(
          (s: { id: { name: string } }) => s.id.name === "RADIOBROWSER"
        );
        expect(rb).to.not.be.undefined;
      });
    });

    it("should include baseUrl in each service", () => {
      cy.request(`${BACKEND}/bmx/registry/v1/services`).then((resp) => {
        const body =
          typeof resp.body === "string" ? JSON.parse(resp.body) : resp.body;
        const services = body.bmx_services || [];
        services.forEach((s: { baseUrl: string }) => {
          expect(s.baseUrl).to.be.a("string");
          expect(s.baseUrl.length).to.be.greaterThan(0);
        });
      });
    });
  });

  // ─── SWUpdate (worldwide.bose.com) ────────────────────────────────────────

  describe("SWUpdate — Firmware Index", () => {
    it("should return firmware INDEX.XML with 200", () => {
      cy.request(`${BACKEND}/updates/soundtouch`).then((resp) => {
        expect(resp.status).to.eq(200);
        expect(resp.headers["content-type"]).to.include("xml");
      });
    });

    it("should contain INDEX root element", () => {
      cy.request(`${BACKEND}/updates/soundtouch`).then((resp) => {
        expect(resp.body).to.include("<INDEX");
        expect(resp.body).to.include("</INDEX>");
      });
    });

    it("should contain SoundTouch device entries", () => {
      cy.request(`${BACKEND}/updates/soundtouch`).then((resp) => {
        // Must have at least SoundTouch 10 (most common device, ID 0x0939)
        expect(resp.body).to.include('ID="0x0939"');
        expect(resp.body).to.include("<DEVICE");
      });
    });

    it("should block firmware downloads with 404", () => {
      cy.request({
        url: `${BACKEND}/ced/eup/downloads/rel/SoundTouch_10.eup`,
        failOnStatusCode: false,
      }).then((resp) => {
        expect(resp.status).to.eq(404);
      });
    });
  });

  // ─── Cross-Domain Integration ─────────────────────────────────────────────

  describe("Cross-Domain — Full Stack", () => {
    it("all three domains respond without errors", () => {
      // Marge
      cy.request(`${BACKEND}/v1/systems/devices/test-device`);
      // BMX
      cy.request(`${BACKEND}/bmx/registry/v1/services`);
      // SWUpdate
      cy.request(`${BACKEND}/updates/soundtouch`);
    });
  });
});
