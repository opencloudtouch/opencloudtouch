/**
 * Accessibility Audit — WCAG 2.1 AA
 *
 * Prüft alle Haupt-Routen der App mit axe-core auf WCAG 2.1 AA Konformität.
 * API-Calls werden intercepted — kein Backend erforderlich.
 *
 * Hinweis: Violations werden gesammelt und in einen Report geschrieben,
 * Tests schlagen NICHT automatisch fehl (skipFailures: true).
 * So können alle Seiten geprüft werden, auch wenn es Violations gibt.
 *
 * Aufruf:
 *   npm run audit:a11y          → generiert tests/e2e/reports/accessibility/
 */

// =============================================================================
// MOCK DATA (identisch mit UX-Screenshot-Tests)
// =============================================================================

const DEVICE_ID_1 = "A1B2C3D4E5F6";
const DEVICE_ID_2 = "B2C3D4E5F6A1";
const NOW = new Date().toISOString();

const MOCK_DEVICES = [
  {
    device_id: DEVICE_ID_1,
    ip: "192.168.1.100",
    name: "Bose SoundTouch 30",
    model: "SoundTouch 30",
    firmware_version: "29.0.3.46291.53",
    mac_address: "A1:B2:C3:D4:E5:F6",
    last_seen: NOW,
  },
  {
    device_id: DEVICE_ID_2,
    ip: "192.168.1.101",
    name: "Bose SoundTouch 10",
    model: "SoundTouch 10",
    firmware_version: "28.1.3.46291.53",
    mac_address: "B2:C3:D4:E5:F6:A1",
    last_seen: NOW,
  },
];

const MOCK_PRESETS = [
  {
    id: 1,
    device_id: DEVICE_ID_1,
    preset_number: 1,
    station_uuid: "uuid-br3",
    station_name: "Bayern 3",
    station_url: "http://br-live.akacast.akamaistream.net/br3_live.mp3",
    source: "LOCAL_INTERNET_RADIO",
    station_homepage: "https://www.br.de/radio/bayern3",
    station_favicon: null,
    created_at: NOW,
    updated_at: NOW,
  },
  {
    id: 2,
    device_id: DEVICE_ID_1,
    preset_number: 2,
    station_uuid: "uuid-wdr2",
    station_name: "WDR 2",
    station_url: "http://wdr-wdr2-rheinland.icecastssl.wdr.de/wdr/wdr2/rheinland/mp3/128/stream.mp3",
    source: "LOCAL_INTERNET_RADIO",
    station_homepage: null,
    station_favicon: null,
    created_at: NOW,
    updated_at: NOW,
  },
];

const MOCK_MANUAL_IPS = ["192.168.1.100", "192.168.1.101"];

// =============================================================================
// SEITEN-KONFIGURATION
// =============================================================================

interface PageConfig {
  name: string;
  path: string;
  setup?: () => void;
  waitFor?: string;
}

const PAGES_WITH_DEVICES: PageConfig[] = [
  {
    name: "Presets (Geräte geladen)",
    path: "/",
    waitFor: '[data-testid="preset-1"]',
  },
  {
    name: "Settings",
    path: "/settings",
    waitFor: ".settings-card, .card, main",
  },
];

const PAGES_WITHOUT_DEVICES: PageConfig[] = [
  {
    name: "Welcome (Onboarding)",
    path: "/welcome",
    waitFor: ".welcome-container, main, h1",
  },
  {
    name: "Presets (Keine Geräte)",
    path: "/",
    waitFor: '[data-test="welcome-title"]',
  },
];

// AXE WCAG 2.1 AA Regeln
const AXE_OPTIONS = {
  runOnly: {
    type: "tag" as const,
    values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"],
  },
  // Bekannte False-Positives ausschließen
  rules: {
    // Framer Motion injiziert aria-hidden auf animated elements
    "aria-hidden-body": { enabled: false },
  },
};

// =============================================================================
// HELPERS
// =============================================================================

function setupMockApiWithDevices(): void {
  cy.intercept("GET", "/api/devices", { body: { devices: MOCK_DEVICES, count: MOCK_DEVICES.length } }).as("getDevices");
  cy.intercept("GET", `/api/presets/${DEVICE_ID_1}`, { body: MOCK_PRESETS }).as("getPresets1");
  cy.intercept("GET", `/api/presets/${DEVICE_ID_2}`, { body: [] }).as("getPresets2");
  cy.intercept("GET", "/api/settings/manual-ips", { body: MOCK_MANUAL_IPS }).as("getManualIPs");
  cy.intercept("POST", "/api/settings/manual-ips", { statusCode: 200, body: {} });
  cy.intercept("DELETE", "/api/settings/manual-ips/*", { statusCode: 200, body: {} });
  cy.intercept("POST", "/api/devices/sync-stream*", { statusCode: 200, body: {} });
  cy.intercept("GET", "/api/devices/discover/stream*", {
    statusCode: 200,
    body: "data: done\n\n",
    headers: { "Content-Type": "text/event-stream" },
  });
  cy.intercept("DELETE", "/api/devices", { statusCode: 200, body: { count: 0 } });
  cy.intercept("POST", "/api/presets/set", { statusCode: 200, body: { message: "OK" } });
  cy.intercept("DELETE", "/api/presets/*", { statusCode: 200, body: { message: "OK" } });
  cy.intercept("GET", "/api/presets/*/sync", { statusCode: 200, body: { message: "Synced" } });
  cy.intercept("GET", "**/radiobrowser*/**", { body: [] });
  cy.intercept("GET", "**/radio-browser*/**", { body: [] });
}

function setupMockApiEmpty(): void {
  cy.intercept("GET", "/api/devices", { body: [] }).as("getDevicesEmpty");
  cy.intercept("GET", "/api/settings/manual-ips", { body: [] }).as("getManualIPs");
  cy.intercept("GET", "/api/devices/discover/stream*", {
    statusCode: 200,
    body: "data: done\n\n",
    headers: { "Content-Type": "text/event-stream" },
  });
}

// =============================================================================
// TESTS
// =============================================================================

describe("Accessibility Audit — WCAG 2.1 AA", () => {
  before(() => {
    cy.task("a11y:clear");
  });

  after(() => {
    cy.task("a11y:report").then((totalViolations) => {
      cy.log(`📋 Report generiert — ${totalViolations} Violations gesamt`);
    });
  });

  // ─── Seiten ohne Geräte ────────────────────────────────────────────────────

  describe("Ohne Geräte (Onboarding-Zustand)", () => {
    beforeEach(() => {
      setupMockApiEmpty();
    });

    for (const page of PAGES_WITHOUT_DEVICES) {
      it(`${page.name} (${page.path})`, () => {
        cy.visit(page.path);
        if (page.waitFor) {
          cy.get(page.waitFor, { timeout: 8000 }).should("exist");
        }
        cy.wait(500);
        cy.injectAxe();

        cy.checkA11y(
          undefined,
          AXE_OPTIONS,
          (violations) => {
            if (violations.length === 0) return;
            cy.log(`⚠️ ${violations.length} WCAG Violation(s) auf ${page.path}`);
            violations.forEach((v) => {
              cy.log(`  [${v.impact?.toUpperCase()}] ${v.id}: ${v.description}`);
            });
            cy.task("a11y:log", {
              page: page.name,
              path: page.path,
              timestamp: new Date().toISOString(),
              violations,
            });
          },
          true // skipFailures: Tests laufen durch, Violations werden nur geloggt
        );
      });
    }
  });

  // ─── Seiten mit Geräten ────────────────────────────────────────────────────

  describe("Mit Geräten (Normal-Zustand)", () => {
    beforeEach(() => {
      setupMockApiWithDevices();
    });

    for (const page of PAGES_WITH_DEVICES) {
      it(`${page.name} (${page.path})`, () => {
        cy.visit(page.path);
        if (page.waitFor) {
          cy.get(page.waitFor, { timeout: 8000 }).should("exist");
        }
        cy.wait(500);
        cy.injectAxe();

        cy.checkA11y(
          undefined,
          AXE_OPTIONS,
          (violations) => {
            if (violations.length === 0) return;
            cy.log(`⚠️ ${violations.length} WCAG Violation(s) auf ${page.path}`);
            violations.forEach((v) => {
              cy.log(`  [${v.impact?.toUpperCase()}] ${v.id}: ${v.description}`);
            });
            cy.task("a11y:log", {
              page: page.name,
              path: page.path,
              timestamp: new Date().toISOString(),
              violations,
            });
          },
          true
        );
      });
    }
  });

  // ─── Interaktive Zustände ──────────────────────────────────────────────────

  describe("Interaktive Zustände", () => {
    it("Manuelle IP Modal — Geöffnet", () => {
      setupMockApiEmpty();
      cy.visit("/welcome");
      cy.wait(500);

      cy.get("body").then(($body) => {
        if ($body.find("details").length > 0) {
          cy.get("details summary").scrollIntoView().click();
          cy.wait(400);
        }
      });

      cy.get("body").then(($body) => {
        if ($body.find('[data-test="manual-add-button"]').length > 0) {
          cy.get('[data-test="manual-add-button"]').scrollIntoView().click({ force: true });
          cy.wait(400);
        }
      });

      cy.injectAxe();
      cy.checkA11y(
        undefined,
        AXE_OPTIONS,
        (violations) => {
          if (violations.length === 0) return;
          cy.task("a11y:log", {
            page: "Manuelle IP Modal",
            path: "/welcome#modal",
            timestamp: new Date().toISOString(),
            violations,
          });
        },
        true
      );
    });

    it("Presets — Leerer Zustand", () => {
      setupMockApiEmpty();
      cy.intercept("GET", "/api/devices", { body: { devices: MOCK_DEVICES, count: MOCK_DEVICES.length } });
      cy.intercept("GET", `/api/presets/${DEVICE_ID_1}`, { body: [] });
      cy.intercept("GET", `/api/presets/${DEVICE_ID_2}`, { body: [] });
      cy.visit("/");
      cy.wait(800);
      cy.injectAxe();
      cy.checkA11y(
        undefined,
        AXE_OPTIONS,
        (violations) => {
          if (violations.length === 0) return;
          cy.task("a11y:log", {
            page: "Presets (Leer)",
            path: "/#empty",
            timestamp: new Date().toISOString(),
            violations,
          });
        },
        true
      );
    });
  });
});
