/**
 * Cypress Accessibility Audit Config
 *
 * Läuft axe-core WCAG 2.1 AA Prüfung gegen alle Haupt-Routen.
 * Benötigt: laufenden Preview-Server auf Port 4173 (npm run preview)
 *
 * Aufruf:
 *   npm run audit:a11y          → headless, generiert Report
 *   npm run audit:a11y:headed   → headed (Debugging)
 */

import { defineConfig } from "cypress";
import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";

const REPORT_DIR = join(__dirname, "tests/e2e/reports/accessibility");
const REPORT_JSON = join(REPORT_DIR, "violations.json");
const REPORT_MD = join(REPORT_DIR, "accessibility-report.md");

interface AxeViolation {
  id: string;
  impact: string;
  description: string;
  help: string;
  helpUrl: string;
  tags: string[];
  nodes: Array<{
    html: string;
    target: string[];
    failureSummary: string;
  }>;
}

interface PageViolations {
  page: string;
  path: string;
  timestamp: string;
  violations: AxeViolation[];
}

const allViolations: PageViolations[] = [];

function generateMarkdownReport(data: PageViolations[]): string {
  const totalViolations = data.reduce((sum, p) => sum + p.violations.length, 0);
  const criticalCount = data.reduce(
    (sum, p) => sum + p.violations.filter((v) => v.impact === "critical").length,
    0
  );
  const seriousCount = data.reduce(
    (sum, p) => sum + p.violations.filter((v) => v.impact === "serious").length,
    0
  );

  const impactEmoji: Record<string, string> = {
    critical: "🔴",
    serious: "🟠",
    moderate: "🟡",
    minor: "⚪",
  };

  let md = `# Accessibility Audit — WCAG 2.1 AA Report

**Erstellt**: ${new Date().toISOString().split("T")[0]}
**Standard**: WCAG 2.1 AA (axe-core)
**Tool**: cypress-axe
**Preview-URL**: http://localhost:4173

---

## Zusammenfassung

| Metrik | Wert |
|--------|------|
| Geprüfte Seiten | ${data.length} |
| Violations gesamt | **${totalViolations}** |
| Kritisch 🔴 | ${criticalCount} |
| Schwerwiegend 🟠 | ${seriousCount} |
| Moderat 🟡 | ${data.reduce((sum, p) => sum + p.violations.filter((v) => v.impact === "moderate").length, 0)} |
| Gering ⚪ | ${data.reduce((sum, p) => sum + p.violations.filter((v) => v.impact === "minor").length, 0)} |

---

`;

  for (const page of data) {
    md += `## ${page.page} (\`${page.path}\`)\n\n`;

    if (page.violations.length === 0) {
      md += `✅ **Keine Violations** — WCAG 2.1 AA bestanden\n\n`;
      continue;
    }

    md += `**${page.violations.length} Violation(s) gefunden:**\n\n`;

    for (const v of page.violations) {
      const emoji = impactEmoji[v.impact] ?? "⚪";
      md += `### ${emoji} \`${v.id}\` — ${v.impact?.toUpperCase()}\n\n`;
      md += `**Beschreibung:** ${v.description}  \n`;
      md += `**Hilfe:** ${v.help}  \n`;
      md += `**WCAG-Tags:** ${v.tags.filter((t) => t.startsWith("wcag")).join(", ")}  \n`;
      md += `**Referenz:** [axe-core Docs](${v.helpUrl})\n\n`;

      if (v.nodes.length > 0) {
        md += `**Betroffene Elemente (${v.nodes.length}):**\n\n`;
        for (const node of v.nodes.slice(0, 3)) {
          md += `\`\`\`html\n${node.html.slice(0, 200)}\n\`\`\`\n`;
          if (node.failureSummary) {
            md += `> ${node.failureSummary.split("\n")[0]}\n\n`;
          }
        }
        if (v.nodes.length > 3) {
          md += `*... und ${v.nodes.length - 3} weitere Elemente*\n\n`;
        }
      }
    }
  }

  return md;
}

export default defineConfig({
  e2e: {
    baseUrl: "http://localhost:4173",
    specPattern: "tests/e2e/audit/**/*.cy.{js,ts}",
    supportFile: "tests/e2e/support/e2e.ts",
    fixturesFolder: false,
    screenshotsFolder: "tests/e2e/screenshots/audit",
    videosFolder: "tests/e2e/videos/audit",
    video: false,
    screenshotOnRunFailure: false,
    scrollBehavior: false,
    setupNodeEvents(on) {
      on("task", {
        "a11y:clear": () => {
          allViolations.length = 0;
          return null;
        },
        "a11y:log": (entry: PageViolations) => {
          allViolations.push(entry);
          return null;
        },
        "a11y:report": () => {
          if (!existsSync(REPORT_DIR)) {
            mkdirSync(REPORT_DIR, { recursive: true });
          }
          writeFileSync(REPORT_JSON, JSON.stringify(allViolations, null, 2), "utf-8");
          const markdown = generateMarkdownReport(allViolations);
          writeFileSync(REPORT_MD, markdown, "utf-8");
          const total = allViolations.reduce((s, p) => s + p.violations.length, 0);
          console.log(`\n📋 Accessibility Report: ${REPORT_MD}`);
          console.log(`   Violations gesamt: ${total}`);
          return total;
        },
      });
    },
    viewportWidth: 1280,
    viewportHeight: 800,
    defaultCommandTimeout: 10000,
    requestTimeout: 10000,
    responseTimeout: 10000,
    numTestsKeptInMemory: 0,
  },
});
