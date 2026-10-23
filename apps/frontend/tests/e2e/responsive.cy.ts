/**
 * E2E: Responsive layout regression suite.
 *
 * Renders every page and every wizard screen at phone/tablet/desktop widths and fails when the
 * layout is broken: content wider than the viewport, overlapping buttons/labels/inputs, or
 * clipped text (see support/layoutAudit.ts for the exact rules).
 *
 * Strategy: the device list and the restore wizard endpoints are mocked with cy.intercept, so the
 * result does not depend on the DB or on real devices. All other calls go to the mock backend
 * (OCT_MOCK_MODE=true), like the other E2E specs. Live-device audits live in tests/real/layout/.
 */
import { collectLayoutIssues, waitForStableLayout, LayoutIssue } from "./support/layoutAudit";
import {
  DEVICES,
  DEVICE,
  SCAN_RESULT,
  RESTORE_RESULT,
  HOSTS_OK,
  FINALIZE_OK,
  VERIFY_ALL_PASSED,
  VERIFY_SOME_FAILED,
  mockApi,
  mockSetupWizardApi,
  visitDe,
} from "./support/wizardMocks";


const PAGE_WIDTHS = [320, 375, 768, 1280];
const WIZARD_WIDTHS = [320, 414, 768, 1280];

const PAGES = [
  { name: "presets", path: `/?device=${DEVICE.device_id}` },
  { name: "local", path: `/local?device=${DEVICE.device_id}` },
  { name: "multiroom", path: "/multiroom" },
  { name: "firmware", path: "/firmware" },
  { name: "settings", path: "/settings" },
  { name: "diagnostics", path: "/diagnostics" },
  { name: "about", path: "/about" },
  { name: "licenses", path: "/licenses" },
];

const WIZARD_SCREENS = [
  { name: "wizard-choice", path: `/setup-wizard?deviceId=${DEVICE.device_id}` },
  ...[2, 3, 4, 5, 6, 7, 8, 9].map((step) => ({
    name: `wizard-step-${step}`,
    path: `/setup-wizard?deviceId=${DEVICE.device_id}&step=${step}`,
  })),
  { name: "restore-choice", path: `/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore` },
];

/** Lets route transitions and data-driven re-renders settle (see waitForStableLayout). */
function settle() {
  cy.get("body").should("be.visible");
  cy.wait(300); // let the first data responses arrive before measuring stability
  cy.window().then((win) => waitForStableLayout(win));
}

function formatIssues(issues: LayoutIssue[]): string {
  return issues
    .map((i) => `[${i.kind}] ${i.selector}${i.other ? ` <-> ${i.other}` : ""} (${i.detail})`)
    .join("\n");
}

function assertNoLayoutIssues(label: string) {
  cy.window().then((win) => {
    const issues = collectLayoutIssues(win);
    expect(issues.length, `${label}: layout issues\n${formatIssues(issues)}`).to.equal(0);
  });
}

/**
 * Wizard frame regressions that are not "overflow": the number inside the active step must stay readable
 * (a global `.step-number` rule from the welcome page once painted it blue on blue), and the content column
 * must keep the 720px width instead of stretching to the old 1200px.
 */
function assertWizardFrame(label: string) {
  cy.get("body").then(($body) => {
    const activeNumber = $body.find(".progress-step.active .step-number")[0];
    if (activeNumber) {
      expect(getComputedStyle(activeNumber).color, `${label}: active step number colour`).to.equal(
        "rgb(255, 255, 255)",
      );
    }
    for (const selector of [".progress-tracker", ".wizard-step"]) {
      const el = $body.find(selector)[0];
      if (el) {
        expect(el.getBoundingClientRect().width, `${label}: ${selector} width`).to.be.at.most(720);
      }
    }
  });
}


const DYNAMIC_WIDTHS = [320, 414, 1280];

describe("Responsive layout", { retries: 0 }, () => {
  describe("pages", () => {
    for (const width of PAGE_WIDTHS) {
      for (const page of PAGES) {
        it(`${page.name} @ ${width}px has no layout defects`, () => {
          mockApi();
          cy.viewport(width, 800);
          visitDe(page.path);
          settle();
          assertNoLayoutIssues(`${page.name}@${width}`);
        });
      }

      it(`welcome (no devices) @ ${width}px has no layout defects`, () => {
        cy.intercept("GET", "/api/devices", { statusCode: 200, body: { count: 0, devices: [] } });
        cy.viewport(width, 800);
        visitDe("/welcome");
        cy.get('[data-test="empty-state"]').should("be.visible");
        settle();
        assertNoLayoutIssues(`welcome@${width}`);
      });
    }
  });

  describe("wizard", () => {
    for (const width of WIZARD_WIDTHS) {
      for (const screen of WIZARD_SCREENS) {
        it(`${screen.name} @ ${width}px has no layout defects`, () => {
          mockApi();
          cy.viewport(width, 800);
          visitDe(screen.path);
          settle();
          assertNoLayoutIssues(`${screen.name}@${width}`);
          assertWizardFrame(`${screen.name}@${width}`);
        });
      }

      it(`restore flow (backup path) @ ${width}px has no layout defects`, () => {
        mockApi();
        cy.intercept("POST", "/api/setup/wizard/scan-backups", { statusCode: 200, body: SCAN_RESULT });
        cy.intercept("POST", "/api/setup/wizard/restore-wizard", { statusCode: 200, body: RESTORE_RESULT });
        cy.viewport(width, 800);
        visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore`);

        // Step 1 -> backup scan
        cy.get(".wizard-choice__card").eq(1).click();
        cy.get(".backup-scan__result").should("be.visible");
        cy.contains(".backup-scan__mismatch", "Erwartete Pfade mit opt/Bose/ wurden im Archiv nicht gefunden").should("exist");
        settle();
        assertNoLayoutIssues(`restore-scan@${width}`);
        assertWizardFrame(`restore-scan@${width}`);

        // Step 2 -> execution (runs automatically, mocked result incl. a failed step)
        cy.get(".wizard-btn-next:not([disabled])").click();
        cy.get(".restore-execution__steps").should("be.visible");
        // Labels and messages are translated from the backend codes (the UI language is German here).
        cy.contains(".restore-execution__label", "Snapshot vor der Wiederherstellung").should("exist");
        cy.contains(".restore-execution__message", "Konfigurationsdateien wiederhergestellt").should("exist");
        cy.contains(".restore-execution__message", "Presets wiederhergestellt unter /mnt/nv/BoseApp-Persistence/1/Presets.xml").should("exist");
        cy.contains(".restore-execution__message", "Wiederherstellung der NTP-Server fehlgeschlagen: Permission denied").should("exist");
        cy.get(".wizard-btn-next:not([disabled])").should("exist");
        settle();
        assertNoLayoutIssues(`restore-execution@${width}`);

        // Step 3 -> verification (device is in the mocked list, so it is detected within ~5 s)
        cy.get(".wizard-btn-next").click();
        cy.get(".restore-verification__countdown, .restore-verification__online").should("exist");
        settle();
        assertNoLayoutIssues(`restore-verification@${width}`);
        cy.get(".restore-verification__online", { timeout: 15000 }).should("be.visible");
        cy.get(".wizard-btn-next:not([disabled])").click();

        // Step 4 -> completion
        cy.get(".restore-completion").should("be.visible");
        settle();
        assertNoLayoutIssues(`restore-completion@${width}`);
        assertWizardFrame(`restore-completion@${width}`);

        // Steps 1-4 are done, so every connector (before steps 2-5) must be green, including the first one.
        // (Connectors are hidden on very narrow screens.)
        if (width > 400) {
          cy.get(".progress-step .step-connector").should("have.length", 4);
          cy.get(".progress-step .step-connector").each(($c) => {
            expect(getComputedStyle($c[0]).backgroundColor, "connector colour").to.equal("rgb(76, 175, 80)");
          });
        }
      });
    }
  });

  describe("restore wizard states (clean path, running, partial failure, timeout)", () => {
    const RESTORE_CLEAN_OK = { ...RESTORE_RESULT, restore_type: "clean" };
    const RESTORE_PARTIAL = {
      ...RESTORE_RESULT,
      restore_type: "clean",
      success: false,
      steps: RESTORE_RESULT.steps.map((step) =>
        step.name === "hosts"
          ? { ...step, status: "failed", message: "Hosts restore failed: Read-only file system", message_code: "hosts_restore_failed", message_params: { error: "Read-only file system" }, error: "Read-only file system" }
          : step,
      ),
    };

    for (const width of DYNAMIC_WIDTHS) {
      it(`clean path shows the skipped backup step, then completes @ ${width}px`, () => {
        mockApi();
        cy.intercept("POST", "/api/setup/wizard/restore-wizard", { statusCode: 200, body: RESTORE_CLEAN_OK });
        cy.viewport(width, 800);
        visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore`);
        cy.get(".wizard-choice__card").eq(0).click();
        cy.get(".restore-execution__steps").should("be.visible");
        cy.get(".progress-step.skipped").should("have.length", 1);
        settle();
        assertNoLayoutIssues(`restore-clean-execution@${width}`);
        assertWizardFrame(`restore-clean-execution@${width}`);

        cy.get(".wizard-btn-next:not([disabled])").click();
        cy.get(".restore-verification__online", { timeout: 15000 }).should("be.visible");
        cy.get(".wizard-btn-next:not([disabled])").click();
        cy.get(".restore-completion").should("be.visible");
        settle();
        assertNoLayoutIssues(`restore-clean-completion@${width}`);
        if (width > 400) {
          // skipped step 2 and completed steps: every connector is green
          cy.get(".progress-step .step-connector").should("have.length", 4);
          cy.get(".progress-step .step-connector").each(($c) => {
            expect(getComputedStyle($c[0]).backgroundColor, "connector colour").to.equal("rgb(76, 175, 80)");
          });
        }
      });

      it(`restore running state (long-running) @ ${width}px`, () => {
        mockApi();
        cy.intercept("POST", "/api/setup/wizard/restore-wizard", { statusCode: 200, body: RESTORE_CLEAN_OK, delay: 3000 });
        cy.viewport(width, 800);
        visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore`);
        cy.get(".wizard-choice__card").eq(0).click();
        cy.get(".restore-execution__progress").should("be.visible");
        // Back is hidden while the restore runs
        cy.get(".wizard-btn-previous").should("not.exist");
        cy.contains(".restore-execution__hint", "mehrere Minuten").should("be.visible");
        settle();
        assertNoLayoutIssues(`restore-running@${width}`);
        assertWizardFrame(`restore-running@${width}`);
        cy.get(".restore-execution__steps", { timeout: 15000 }).should("be.visible");
      });

      it(`restore partial failure @ ${width}px`, () => {
        mockApi();
        cy.intercept("POST", "/api/setup/wizard/restore-wizard", { statusCode: 200, body: RESTORE_PARTIAL });
        cy.viewport(width, 800);
        visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore`);
        cy.get(".wizard-choice__card").eq(0).click();
        cy.get(".restore-execution__failed").should("be.visible");
        cy.contains(".restore-execution__message", "Wiederherstellung von /etc/hosts fehlgeschlagen: Read-only file system").should("exist");
        cy.get(".restore-execution__success").should("not.exist");
        if (width >= 414) {
          // A long German label must stay on one line (it once broke mid-word because the duration shared its row).
          cy.contains(".restore-execution__label", "Konfigurationsdateien").then(($label) => {
            expect($label[0].getBoundingClientRect().height, "label height (one line)").to.be.lessThan(30);
          });
        }
        // There is no Next button after a failed restore (onNext is only set on success); Back is available to try again
        cy.get(".wizard-btn-next").should("not.exist");
        cy.get(".wizard-btn-previous").should("be.visible");
        settle();
        assertNoLayoutIssues(`restore-partial@${width}`);
        assertWizardFrame(`restore-partial@${width}`);
      });

      it(`restore verification timeout @ ${width}px`, () => {
        mockApi();
        cy.intercept("POST", "/api/setup/wizard/restore-wizard", { statusCode: 200, body: RESTORE_CLEAN_OK });
        // The 120 s countdown ticks every 5 s: fake only the interval timers and tick instead of waiting.
        cy.clock(Date.now(), ["setInterval", "clearInterval"]);
        cy.viewport(width, 800);
        visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore`);
        cy.get(".wizard-choice__card").eq(0).click();
        cy.get(".restore-execution__steps").should("be.visible");
        // From now on the poll no longer finds the device (its IP changed), so the countdown runs out.
        cy.intercept("GET", "/api/devices", {
          statusCode: 200,
          body: { count: 1, devices: [{ ...DEVICE, ip: "10.9.9.9" }] },
        });
        cy.get(".wizard-btn-next:not([disabled])").click();
        cy.get(".restore-verification__countdown").should("be.visible");
        settle();
        assertNoLayoutIssues(`restore-countdown@${width}`);

        cy.tick(5000 * 25);
        cy.get(".restore-verification__timeout").should("be.visible");
        cy.get(".restore-verification__timeout button").should("have.length", 2);
        settle();
        assertNoLayoutIssues(`restore-timeout@${width}`);
        assertWizardFrame(`restore-timeout@${width}`);
      });
    }
  });

  describe("wizard dynamic states (setup steps 5-8)", () => {
    for (const width of DYNAMIC_WIDTHS) {
      it(`hosts step: error, retry and success with diff @ ${width}px`, () => {
        mockSetupWizardApi();
        cy.intercept("POST", "/api/setup/wizard/modify-hosts", { statusCode: 200, body: { success: false, message: "Could not write /etc/hosts" } }).as("hostsFail");
        cy.viewport(width, 800);
        visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&step=6`);
        settle();
        assertNoLayoutIssues(`hosts-form@${width}`);

        cy.get("button.hosts-modify-btn").click();
        cy.get(".hosts-error").should("be.visible");
        settle();
        assertNoLayoutIssues(`hosts-error@${width}`);
        // The form stays so a failed attempt can be repeated.
        cy.get("button.hosts-modify-btn").should("be.visible");

        cy.intercept("POST", "/api/setup/wizard/modify-hosts", { statusCode: 200, body: HOSTS_OK });
        cy.get("button.hosts-modify-btn").click();
        cy.get(".hosts-success").should("be.visible");
        settle();
        assertNoLayoutIssues(`hosts-success@${width}`);
        cy.get("button.hosts-diff-toggle").click();
        cy.get("pre.hosts-diff").should("be.visible");
        settle();
        assertNoLayoutIssues(`hosts-diff@${width}`);
        assertWizardFrame(`hosts@${width}`);
      });

      it(`ntp step: error and success @ ${width}px`, () => {
        mockSetupWizardApi();
        cy.intercept("POST", "/api/setup/wizard/patch-ntp", { statusCode: 200, body: { success: false, message: "Permission denied while writing /etc/ntpservers.txt" } });
        cy.viewport(width, 800);
        visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&step=7`);
        settle();
        assertNoLayoutIssues(`ntp-form@${width}`);

        cy.get("button.ntp-patch-btn").click();
        cy.get(".ntp-error").should("be.visible");
        settle();
        assertNoLayoutIssues(`ntp-error@${width}`);

        cy.intercept("POST", "/api/setup/wizard/patch-ntp", { statusCode: 200, body: { success: true, message: "NTP server set to pool.ntp.org" } });
        cy.get("button.ntp-patch-btn").click();
        cy.get(".ntp-success").should("be.visible");
        settle();
        assertNoLayoutIssues(`ntp-success@${width}`);
      });

      for (const [label, verifyBody, allPassed] of [
        ["all checks passed", VERIFY_ALL_PASSED, true],
        ["some checks failed", VERIFY_SOME_FAILED, false],
      ] as const) {
        it(`verification step: finalize, reboot countdown, results (${label}) @ ${width}px`, () => {
          mockSetupWizardApi();
          cy.intercept("POST", "/api/setup/wizard/verify-setup", { statusCode: 200, body: verifyBody });
          // The reboot countdown runs 100 s via setInterval. Fake only the interval timers (not Date or
          // requestAnimationFrame, which waitForStableLayout and framer-motion need) and tick instead of waiting.
          cy.clock(Date.now(), ["setInterval", "clearInterval"]);
          cy.viewport(width, 800);
          visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&step=8`);
          settle();
          assertNoLayoutIssues(`verify-idle@${width}`);

          cy.get(".finalize-section .btn").click();
          cy.get(".reboot-btn").should("be.visible");
          settle();
          assertNoLayoutIssues(`verify-finalized@${width}`);

          cy.get(".reboot-btn").click();
          cy.get(".reboot-status--waiting").should("be.visible");
          settle();
          assertNoLayoutIssues(`verify-countdown@${width}`);

          cy.tick(101000);
          cy.get(".verification-test-btn").should("be.visible");
          settle();
          assertNoLayoutIssues(`verify-start@${width}`);

          cy.get(".verification-test-btn").click();
          cy.get(allPassed ? ".verification-success" : ".verification-failed").should("be.visible");
          settle();
          assertNoLayoutIssues(`verify-results@${width}`);
          assertWizardFrame(`verify@${width}`);
          if (allPassed) {
            cy.get(".wizard-btn-next").should("not.be.disabled");
          } else {
            cy.get(".verification-retry-btn").should("be.visible");
            cy.get(".wizard-btn-next").should("be.disabled");
          }
        });
      }
    }
  });
});
