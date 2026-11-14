import { describe, it, expect } from "vitest";
import {
  compressRanges,
  groupIssues,
  themeScope,
  formatMarkdown,
  formatConsole,
  screenshotName,
  shouldScreenshot,
  type AuditRecord,
} from "../../e2e/support/uiAudit/report";

const overflow = (width: number, theme: "dark" | "light", page = "/settings"): AuditRecord => ({
  page,
  theme,
  width,
  issues: [
    {
      kind: "edge-overflow",
      selector: 'span.nav-label "Einstellungen"',
      detail: `right ${width + 4} (viewport ${width})`,
    },
  ],
});

describe("compressRanges", () => {
  it("joins consecutive numbers and keeps gaps", () => {
    expect(compressRanges([320, 321, 322, 340, 341, 360])).toBe("320–322, 340–341, 360");
  });
  it("sorts and de-duplicates", () => {
    expect(compressRanges([361, 360, 360, 359])).toBe("359–361");
  });
  it("handles one value and none", () => {
    expect(compressRanges([320])).toBe("320");
    expect(compressRanges([])).toBe("");
  });
});

describe("groupIssues", () => {
  it("merges the same defect across widths, pages and themes", () => {
    const groups = groupIssues([
      overflow(320, "light"),
      overflow(321, "light"),
      overflow(320, "dark"),
      overflow(320, "light", "/about"),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0]).toMatchObject({
      kind: "edge-overflow",
      pages: ["/about", "/settings"],
      themes: ["dark", "light"],
      widths: [320, 321],
      count: 4,
    });
    expect(groups[0]?.example).toContain("viewport 320");
  });
  it("keeps different selectors and kinds apart and ignores clean records", () => {
    const groups = groupIssues([
      overflow(320, "light"),
      { page: "/", theme: "dark", width: 320, issues: [] },
      {
        page: "/",
        theme: "dark",
        width: 320,
        issues: [{ kind: "contrast", selector: "p.x", detail: "2.1:1 < 4.5:1" }],
      },
    ]);
    expect(groups.map((g) => g.kind).sort()).toEqual(["contrast", "edge-overflow"]);
  });
  it("lists the largest problems first", () => {
    const groups = groupIssues([
      {
        page: "/",
        theme: "dark",
        width: 320,
        issues: [{ kind: "contrast", selector: "a", detail: "d" }],
      },
      overflow(320, "dark"),
      overflow(321, "dark"),
    ]);
    expect(groups[0]?.kind).toBe("edge-overflow");
  });
});

describe("themeScope", () => {
  it("says where a defect shows up", () => {
    expect(themeScope(["light"])).toBe("light only");
    expect(themeScope(["dark"])).toBe("dark only");
    expect(themeScope(["dark", "light"])).toBe("both themes");
  });
});

describe("formatMarkdown and formatConsole", () => {
  const groups = groupIssues([overflow(320, "light"), overflow(340, "light")]);
  const meta = { pages: 2, themes: 2, widths: 12, checks: 48 };
  it("lists kind, selector, widths and scope", () => {
    const md = formatMarkdown(groups, meta);
    expect(md).toContain("edge-overflow");
    expect(md).toContain("Einstellungen");
    expect(md).toContain("320, 340");
    expect(md).toContain("light only");
    expect(md).toContain("48");
  });
  it("says so when nothing was found", () => {
    expect(formatMarkdown([], meta)).toContain("No issues");
    expect(formatConsole([], meta)).toContain("No issues");
  });
  it("prints one line per group to the console", () => {
    const text = formatConsole(groups, meta);
    expect(text.split("\n").filter((l) => l.includes("edge-overflow"))).toHaveLength(1);
  });
});

describe("screenshotName", () => {
  it("builds a flat, readable file name", () => {
    expect(screenshotName("/about", "light", 320)).toBe("about__light__320.png");
    expect(screenshotName("/", "dark", 1280)).toBe("home__dark__1280.png");
    expect(screenshotName("/setup-wizard", "dark", 375)).toBe("setup-wizard__dark__375.png");
  });
  it("turns state ids with query strings and separators into safe names", () => {
    expect(screenshotName("/setup-wizard?step=3", "dark", 320)).toBe(
      "setup-wizard-step-3__dark__320.png"
    );
    expect(screenshotName("/multiroom#create dialog: step 2", "light", 375)).toBe(
      "multiroom-create-dialog-step-2__light__375.png"
    );
  });
});

describe("shouldScreenshot", () => {
  const base = [320, 375, 1280];
  it("shoots the base widths always", () => {
    expect(shouldScreenshot(375, base, false)).toBe(true);
  });
  it("shoots other widths only when something was found", () => {
    expect(shouldScreenshot(359, base, false)).toBe(false);
    expect(shouldScreenshot(359, base, true)).toBe(true);
  });
});
