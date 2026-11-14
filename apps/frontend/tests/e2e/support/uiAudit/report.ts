/** Aggregation and formatting of UI audit results. */

export interface AuditIssue {
  kind: string;
  selector: string;
  other?: string;
  detail: string;
}

export interface AuditRecord {
  page: string;
  theme: "dark" | "light";
  width: number;
  issues: AuditIssue[];
}

export interface IssueGroup {
  kind: string;
  selector: string;
  other?: string;
  pages: string[];
  themes: string[];
  widths: number[];
  count: number;
  example: string;
}

export interface ReportMeta {
  pages: number;
  themes: number;
  widths: number;
  checks: number;
}

/** [320, 321, 340] -> "320–321, 340". */
export function compressRanges(values: number[]): string {
  const sorted = [...new Set(values)].sort((a, b) => a - b);
  const parts: string[] = [];
  for (let i = 0; i < sorted.length; ) {
    let j = i;
    while (j + 1 < sorted.length && (sorted[j + 1] as number) === (sorted[j] as number) + 1) j++;
    parts.push(j > i ? `${sorted[i]}–${sorted[j]}` : `${sorted[i]}`);
    i = j + 1;
  }
  return parts.join(", ");
}

/** Merges the same defect (kind + element) seen at different widths, pages and themes. */
export function groupIssues(records: AuditRecord[]): IssueGroup[] {
  const map = new Map<string, IssueGroup>();
  for (const rec of records) {
    for (const issue of rec.issues) {
      const key = `${issue.kind}|${issue.selector}|${issue.other ?? ""}`;
      let group = map.get(key);
      if (!group) {
        group = {
          kind: issue.kind,
          selector: issue.selector,
          other: issue.other,
          pages: [],
          themes: [],
          widths: [],
          count: 0,
          example: issue.detail,
        };
        map.set(key, group);
      }
      group.count++;
      if (!group.pages.includes(rec.page)) group.pages.push(rec.page);
      if (!group.themes.includes(rec.theme)) group.themes.push(rec.theme);
      if (!group.widths.includes(rec.width)) group.widths.push(rec.width);
    }
  }
  const groups = [...map.values()];
  for (const g of groups) {
    g.pages.sort();
    g.themes.sort();
    g.widths.sort((a, b) => a - b);
  }
  return groups.sort((a, b) => b.count - a.count || a.kind.localeCompare(b.kind));
}

export function themeScope(themes: string[]): string {
  if (themes.length > 1) return "both themes";
  return `${themes[0]} only`;
}

const elementLabel = (g: IssueGroup) => (g.other ? `${g.selector} ↔ ${g.other}` : g.selector);
const cell = (text: string) => text.replace(/\|/g, "\\|");

export function formatMarkdown(groups: IssueGroup[], meta: ReportMeta): string {
  const head = [
    "# UI audit",
    "",
    `${meta.pages} pages × ${meta.themes} themes × ${meta.widths} widths = ${meta.checks} checks.`,
    "",
  ];
  if (groups.length === 0) return [...head, "No issues found."].join("\n") + "\n";
  const rows = groups.map(
    (g) =>
      `| ${g.kind} | ${cell(elementLabel(g))} | ${themeScope(g.themes)} | ${g.pages.join(", ")} | ${compressRanges(g.widths)} | ${cell(g.example)} |`
  );
  return (
    [
      ...head,
      `${groups.length} distinct issues.`,
      "",
      "| Kind | Element | Scope | Pages | Widths (px) | Example |",
      "| --- | --- | --- | --- | --- | --- |",
      ...rows,
    ].join("\n") + "\n"
  );
}

export function formatConsole(groups: IssueGroup[], meta: ReportMeta): string {
  const head = `UI audit: ${meta.pages} pages x ${meta.themes} themes x ${meta.widths} widths = ${meta.checks} checks`;
  if (groups.length === 0) return `${head}\nNo issues found.`;
  const lines = groups.map(
    (g) =>
      `  [${g.kind}] ${elementLabel(g)} | ${themeScope(g.themes)} | ${g.pages.join(", ")} | ${compressRanges(g.widths)}px | ${g.example}`
  );
  return [head, `${groups.length} distinct issues:`, ...lines].join("\n");
}

export function screenshotName(page: string, theme: string, width: number): string {
  const slug =
    page
      .replace(/^\/+/, "")
      .replace(/[^A-Za-z0-9_]+/g, "-")
      .replace(/^-+|-+$/g, "") || "home";
  return `${slug}__${theme}__${width}.png`;
}

export function shouldScreenshot(width: number, baseWidths: number[], hasIssues: boolean): boolean {
  return baseWidths.includes(width) || hasIssues;
}
