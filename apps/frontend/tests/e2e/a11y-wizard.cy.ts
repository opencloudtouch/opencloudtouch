/**
 * Accessibility (axe-core) for every wizard screen and for the dynamic states (errors, success boxes,
 * warnings, verification results, restore flow). Fails on critical, serious and moderate violations.
 *
 * The device list and the wizard endpoints are mocked (support/wizardMocks.ts), everything else goes to
 * the mock backend like the other E2E specs.
 */
import {
  DEVICE,
  RESTORE_RESULT,
  SCAN_RESULT,
  HOSTS_OK,
  VERIFY_ALL_PASSED,
  VERIFY_SOME_FAILED,
  mockApi,
  mockSetupWizardApi,
  visitDe,
} from "./support/wizardMocks";

const SCREENS = [
  { name: "choice", path: `/setup-wizard?deviceId=${DEVICE.device_id}` },
  ...[2, 3, 4, 5, 6, 7, 8, 9].map((step) => ({
    name: `setup-step-${step}`,
    path: `/setup-wizard?deviceId=${DEVICE.device_id}&step=${step}`,
  })),
  { name: "restore-choice", path: `/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore` },
];

type AxeViolation = { id: string; impact?: string | null; help: string; nodes: { target: unknown }[] };

function formatViolations(violations: AxeViolation[]): string {
  return violations
    .map(
      (v) =>
        `[${v.impact}] ${v.id}: ${v.help} (${v.nodes.length}x) -> ` +
        v.nodes.slice(0, 3).map((n) => JSON.stringify(n.target)).join(", "),
    )
    .join("\n");
}

/** Waits until all finite CSS/JS animations have finished (looping ones such as spinners are ignored). */
function waitForAnimationsToFinish() {
  cy.window().should((win) => {
    const running = win.document
      .getAnimations()
      .filter((a) => a.playState === "running" && a.effect?.getComputedTiming().iterations !== Infinity);
    expect(running, "running finite animations").to.have.lengthOf(0);
  });
}

/** Runs axe on the current page; fails with a readable list of violations. */
function assertNoAxeViolations(label: string) {
  waitForAnimationsToFinish(); // slide/fade animations must finish so contrast is measured on settled colours
  cy.injectAxe();
  let found: AxeViolation[] = [];
  // skipFailures: collect first, then fail with a readable message (the default message omits the details)
  cy.checkA11y(
    undefined,
    { includedImpacts: ["critical", "serious", "moderate"] },
    (violations) => {
      found = violations as unknown as AxeViolation[];
    },
    true,
  );
  cy.then(() => {
    expect(found, `axe violations on ${label}\n${formatViolations(found)}`).to.have.lengthOf(0);
  });
}

describe("Accessibility: wizard screens", { retries: 0 }, () => {
  beforeEach(() => {
    mockApi();
  });

  for (const width of [375, 1280]) {
    for (const screen of SCREENS) {
      it(`${screen.name} @ ${width}px has no axe violations`, () => {
        cy.viewport(width, 800);
        visitDe(screen.path);
        cy.get(".wizard-step, .wizard-choice__cards", { timeout: 10000 }).should("exist");
        assertNoAxeViolations(`${screen.name}@${width}`);
      });
    }
  }
});

describe("Accessibility: wizard dynamic states", { retries: 0 }, () => {
  const PARTIAL = { ...RESTORE_RESULT, success: false };

  for (const width of [375, 1280]) {
    it(`restore flow (backup path: scan, execution, verification, completion) @ ${width}px`, () => {
      mockApi();
      cy.intercept("POST", "/api/setup/wizard/scan-backups", { statusCode: 200, body: SCAN_RESULT });
      cy.intercept("POST", "/api/setup/wizard/restore-wizard", { statusCode: 200, body: RESTORE_RESULT });
      cy.viewport(width, 800);
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore`);

      cy.get(".wizard-choice__card").eq(1).click();
      cy.get(".backup-scan__result").should("be.visible");
      assertNoAxeViolations(`restore-scan@${width}`);

      cy.get(".wizard-btn-next:not([disabled])").click();
      cy.get(".restore-execution__steps").should("be.visible");
      assertNoAxeViolations(`restore-execution (with a failed step)@${width}`);

      cy.get(".wizard-btn-next:not([disabled])").click();
      cy.get(".restore-verification__online", { timeout: 15000 }).should("be.visible");
      assertNoAxeViolations(`restore-verification-online@${width}`);

      cy.get(".wizard-btn-next:not([disabled])").click();
      cy.get(".restore-completion").should("be.visible");
      assertNoAxeViolations(`restore-completion@${width}`);
    });

    it(`restore running and partial failure @ ${width}px`, () => {
      mockApi();
      cy.intercept("POST", "/api/setup/wizard/restore-wizard", { statusCode: 200, body: PARTIAL, delay: 2500 });
      cy.viewport(width, 800);
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore`);
      cy.get(".wizard-choice__card").eq(0).click();
      cy.get(".restore-execution__progress").should("be.visible");
      assertNoAxeViolations(`restore-running@${width}`);
      cy.get(".restore-execution__failed", { timeout: 15000 }).should("be.visible");
      assertNoAxeViolations(`restore-partial-failure@${width}`);
    });

    it(`restore verification countdown and timeout @ ${width}px`, () => {
      mockApi();
      cy.intercept("POST", "/api/setup/wizard/restore-wizard", {
        statusCode: 200,
        body: { ...RESTORE_RESULT, success: true, restore_type: "clean" },
      });
      cy.clock(Date.now(), ["setInterval", "clearInterval"]);
      cy.viewport(width, 800);
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&mode=restore`);
      cy.get(".wizard-choice__card").eq(0).click();
      cy.get(".restore-execution__steps").should("be.visible");
      cy.intercept("GET", "/api/devices", {
        statusCode: 200,
        body: { count: 1, devices: [{ ...DEVICE, ip: "10.9.9.9" }] },
      });
      cy.get(".wizard-btn-next:not([disabled])").click();
      cy.get(".restore-verification__countdown").should("be.visible");
      assertNoAxeViolations(`restore-countdown@${width}`);
      cy.tick(5000 * 25);
      cy.get(".restore-verification__timeout").should("be.visible");
      assertNoAxeViolations(`restore-timeout@${width}`);
    });

    it(`hosts and NTP step: errors and success @ ${width}px`, () => {
      mockSetupWizardApi();
      cy.intercept("POST", "/api/setup/wizard/modify-hosts", { statusCode: 200, body: { success: false, message: "Could not write /etc/hosts" } });
      cy.viewport(width, 800);
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&step=6`);
      cy.get("button.hosts-modify-btn").click();
      cy.get(".hosts-error").should("be.visible");
      assertNoAxeViolations(`hosts-error@${width}`);
      cy.intercept("POST", "/api/setup/wizard/modify-hosts", { statusCode: 200, body: HOSTS_OK });
      cy.get("button.hosts-modify-btn").click();
      cy.get(".hosts-success").should("be.visible");
      cy.get("button.hosts-diff-toggle").click();
      assertNoAxeViolations(`hosts-success-with-diff@${width}`);

      cy.intercept("POST", "/api/setup/wizard/patch-ntp", { statusCode: 200, body: { success: false, message: "Permission denied" } });
      visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&step=7`);
      cy.get("button.ntp-patch-btn").click();
      cy.get(".ntp-error").should("be.visible");
      assertNoAxeViolations(`ntp-error@${width}`);
      cy.intercept("POST", "/api/setup/wizard/patch-ntp", { statusCode: 200, body: { success: true, message: "NTP server set" } });
      cy.get("button.ntp-patch-btn").click();
      cy.get(".ntp-success").should("be.visible");
      assertNoAxeViolations(`ntp-success@${width}`);
    });

    for (const [label, verifyBody, passed] of [
      ["all checks passed", VERIFY_ALL_PASSED, true],
      ["some checks failed", VERIFY_SOME_FAILED, false],
    ] as const) {
      it(`verification step (${label}) @ ${width}px`, () => {
        mockSetupWizardApi();
        cy.intercept("POST", "/api/setup/wizard/verify-setup", { statusCode: 200, body: verifyBody });
        cy.clock(Date.now(), ["setInterval", "clearInterval"]);
        cy.viewport(width, 800);
        visitDe(`/setup-wizard?deviceId=${DEVICE.device_id}&step=8`);
        cy.get(".finalize-section .btn").click();
        cy.get(".reboot-btn").scrollIntoView().should("be.visible");
        assertNoAxeViolations(`verify-finalized@${width}`);
        cy.get(".reboot-btn").click();
        cy.get(".reboot-status--waiting").should("be.visible");
        assertNoAxeViolations(`verify-countdown@${width}`);
        cy.tick(101000);
        cy.get(".verification-test-btn").click();
        cy.get(passed ? ".verification-success" : ".verification-failed").scrollIntoView().should("be.visible");
        assertNoAxeViolations(`verify-results-${label}@${width}`);
      });
    }
  }
});
