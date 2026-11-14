/**
 * Cypress UI audit: every page x theme (dark, light) x viewport width, including both sides of every
 * CSS width breakpoint. Measures layout collisions, text leaving its control, contrast (own
 * measurement plus axe) and writes screenshots and a report.
 *
 * Needs the preview server on port 4173; API calls are mocked.
 *   npm run audit:ui                       build, serve, run, print the findings
 *   UI_AUDIT_WIDTHS=320,375 npm run audit:ui   limit the widths (comma separated)
 *
 * Output: ../../.out/reports/ui-audit/ (report.md, report.json, screenshots/)
 */
import { defineConfig } from "cypress";
import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { buildWidthMatrix, extractBreakpoints } from "./tests/e2e/support/uiAudit/viewports";
import {
  formatConsole,
  formatMarkdown,
  groupIssues,
  type AuditRecord,
} from "./tests/e2e/support/uiAudit/report";

const here = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(here, "../../.out/reports/ui-audit");
const BASE_WIDTHS = [320, 375, 414, 600, 768, 1024, 1280, 1920];

const records: AuditRecord[] = [];

function cssFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? cssFiles(path) : path.endsWith(".css") ? [path] : [];
  });
}

function widthMatrix(): { widths: number[]; base: number[] } {
  const override = process.env.UI_AUDIT_WIDTHS;
  if (override) {
    const widths = override
      .split(",")
      .map((w) => parseInt(w, 10))
      .filter(Number.isFinite);
    return { widths, base: widths };
  }
  const css = cssFiles(join(here, "src"))
    .map((f) => readFileSync(f, "utf-8"))
    .join("\n");
  const breakpoints = extractBreakpoints(css);
  return {
    widths: buildWidthMatrix(breakpoints, { min: 320, max: 1920, base: BASE_WIDTHS }),
    base: BASE_WIDTHS,
  };
}

export default defineConfig({
  e2e: {
    baseUrl: "http://localhost:4173",
    specPattern: "tests/e2e/ui-audit/**/*.cy.ts",
    supportFile: "tests/e2e/support/e2e.ts",
    fixturesFolder: false,
    screenshotsFolder: join(OUT_DIR, "screenshots"),
    video: false,
    screenshotOnRunFailure: false,
    scrollBehavior: false,
    viewportWidth: 1280,
    viewportHeight: 800,
    defaultCommandTimeout: 10000,
    numTestsKeptInMemory: 0,
    setupNodeEvents(on) {
      on("before:browser:launch", (browser, launchOptions) => {
        if (browser.family === "chromium") {
          launchOptions.args.push("--force-device-scale-factor=1", "--no-sandbox");
        }
        return launchOptions;
      });
      on("task", {
        "uiAudit:matrix": () => widthMatrix(),
        "uiAudit:record": (record: AuditRecord) => {
          records.push(record);
          return null;
        },
        "uiAudit:reset": () => {
          records.length = 0;
          return null;
        },
        "uiAudit:report": (meta: { pages: number; themes: number; widths: number }) => {
          const full = { ...meta, checks: records.length };
          const groups = groupIssues(records);
          mkdirSync(OUT_DIR, { recursive: true });
          writeFileSync(join(OUT_DIR, "report.md"), formatMarkdown(groups, full), "utf-8");
          writeFileSync(join(OUT_DIR, "report.json"), JSON.stringify(groups, null, 2), "utf-8");
          console.log("\n" + formatConsole(groups, full));
          console.log(`Report: ${join(OUT_DIR, "report.md")}`);
          return groups.length;
        },
      });
    },
  },
});
