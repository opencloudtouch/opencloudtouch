/**
 * Read-only live audit for the final consistency review (exploratory, not for CI).
 * Visits every page in every language and several viewport widths, records layout issues,
 * console errors, raw i18n keys and a few computed style metrics for the consistency comparison.
 *
 * Run: npx cypress run --spec tests/real/layout/stage14-live-audit.cy.ts --config baseUrl=http://hera:7778
 * Output: tests/e2e/reports/stage14-live-audit.json and screenshots/stage14.
 */
import { collectLayoutIssues, waitForStableLayout, LayoutIssue } from "../../e2e/support/layoutAudit";

const DEVICE = "68C90B32AF6E";
const LANGS = ["en", "de", "fr", "it", "es", "nl", "pt-BR", "ja", "pl", "sv"];
const PAGES: { name: string; path: string }[] = [
  { name: "devices", path: `/?device=${DEVICE}` },
  { name: "zones", path: "/multiroom" },
  { name: "firmware", path: "/firmware" },
  { name: "settings", path: "/settings" },
  { name: "diagnostics", path: "/diagnostics" },
  { name: "info", path: "/about" },
  { name: "licenses", path: "/licenses" },
  { name: "notfound", path: "/does-not-exist" },
];
// Every language at the two extremes, English at all widths.
const MATRIX: { lang: string; width: number }[] = [
  ...LANGS.flatMap((lang) => [1440, 320].map((width) => ({ lang, width }))),
  ...[1024, 900, 768, 390].map((width) => ({ lang: "en", width })),
];

interface Metrics {
  h1Text: string;
  h1Size: string;
  h1Left: number;
  contentLeft: number;
  contentWidth: number;
  navLeft: number;
  scrollOverflow: boolean;
  rawKeys: string[];
  consoleErrors: string[];
  issues: LayoutIssue[];
}
const results: Record<string, Metrics> = {};

describe("Stage 14 live audit", () => {
  after(() => {
    cy.writeFile("tests/e2e/reports/stage14-live-audit.json", results);
  });

  for (const { lang, width } of MATRIX) {
    for (const page of PAGES) {
      it(`${page.name} ${lang} @ ${width}px`, () => {
        const errors: string[] = [];
        cy.viewport(width, 900);
        cy.visit(page.path, {
          onBeforeLoad(win) {
            win.localStorage.setItem("oct-lang", lang);
            const orig = win.console.error.bind(win.console);
            win.console.error = (...args: unknown[]) => {
              errors.push(args.map(String).join(" ").slice(0, 200));
              orig(...args);
            };
          },
        });
        cy.get("body").should("be.visible");
        cy.window().then((win) => waitForStableLayout(win));
        cy.window().then((win) => {
          const doc = win.document;
          const h1 = doc.querySelector("h1");
          const main = doc.querySelector("main") as HTMLElement | null;
          const nav = doc.querySelector(".nav-container") as HTMLElement | null;
          const first = (main?.firstElementChild as HTMLElement | null) ?? main;
          const rawKeys = Array.from(doc.querySelectorAll("body *"))
            .filter((el) => el.children.length === 0)
            .map((el) => (el.textContent ?? "").trim())
            .filter((txt) => /^[a-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+){1,}$/.test(txt))
            .slice(0, 5);
          results[`${page.name}|${lang}|${width}`] = {
            h1Text: h1?.textContent?.trim() ?? "",
            h1Size: h1 ? win.getComputedStyle(h1).fontSize : "",
            h1Left: h1 ? Math.round(h1.getBoundingClientRect().left) : -1,
            contentLeft: first ? Math.round(first.getBoundingClientRect().left) : -1,
            contentWidth: first ? Math.round(first.getBoundingClientRect().width) : -1,
            navLeft: nav ? Math.round(nav.getBoundingClientRect().left) : -1,
            scrollOverflow: doc.documentElement.scrollWidth > win.innerWidth,
            rawKeys,
            consoleErrors: errors.slice(0, 5),
            issues: collectLayoutIssues(win),
          };
        });
        if (lang === "en" || lang === "de" || lang === "ja") {
          cy.screenshot(`stage14/${page.name}-${lang}-${width}`, { capture: "fullPage" });
        }
      });
    }
  }
});
