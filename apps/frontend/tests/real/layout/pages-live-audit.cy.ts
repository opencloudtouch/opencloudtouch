/**
 * Responsive audit (exploratory): visits every top-level page at several viewport
 * widths against a live server, records layout issues and takes screenshots.
 * Results go to tests/e2e/reports/responsive-audit.json.
 *
 * Run: npx cypress run --spec tests/real/layout/pages-live-audit.cy.ts \
 *        --config baseUrl=http://hera:7778
 */
import {
  collectLayoutIssues,
  waitForStableLayout,
  LayoutIssue,
} from "../../e2e/support/layoutAudit";

const VIEWPORTS = [320, 375, 768, 1280];
const DEVICE = "68C90B32AF6E";
const PAGES: { name: string; path: string }[] = [
  { name: "presets", path: `/?device=${DEVICE}` },
  { name: "local", path: "/local" },
  { name: "multiroom", path: "/multiroom" },
  { name: "firmware", path: "/firmware" },
  { name: "settings", path: "/settings" },
  { name: "diagnostics", path: "/diagnostics" },
  { name: "about", path: "/about" },
  { name: "licenses", path: "/licenses" },
];

const results: Record<string, LayoutIssue[]> = {};

describe("Responsive audit", () => {
  after(() => {
    cy.writeFile("tests/e2e/reports/responsive-audit.json", results);
  });

  for (const width of VIEWPORTS) {
    for (const page of PAGES) {
      it(`${page.name} @ ${width}px`, () => {
        cy.viewport(width, 800);
        cy.visit(page.path);
        cy.get("body").should("be.visible");
        cy.window().then((win) => waitForStableLayout(win));
        cy.window().then((win) => {
          results[`${page.name}@${width}`] = collectLayoutIssues(win);
        });
        cy.screenshot(`responsive/${page.name}-${width}`, { capture: "fullPage" });
      });
    }
  }
});
