import { describe, it, expect } from "vitest";
import { extractBreakpoints, buildWidthMatrix } from "../../e2e/support/uiAudit/viewports";

describe("extractBreakpoints", () => {
  it("finds min-width and max-width in px, sorted and unique", () => {
    const css = `
      @media (min-width: 601px) { a { color: red } }
      @media (max-width:360px) { a { color: red } }
      @media (min-width: 601px) { b { color: red } }`;
    expect(extractBreakpoints(css)).toEqual([360, 601]);
  });
  it("finds both sides of a combined query", () => {
    expect(extractBreakpoints("@media (min-width: 769px) and (max-width: 900px) {}")).toEqual([
      769, 900,
    ]);
  });
  it("converts em and rem to px", () => {
    expect(extractBreakpoints("@media (min-width: 40em) {} @media (max-width: 30rem) {}")).toEqual([
      480, 640,
    ]);
  });
  it("ignores queries that are not about the width", () => {
    const css =
      "@media (prefers-reduced-motion: reduce) {} @media (min-height: 700px) {} @media (hover: hover) {}";
    expect(extractBreakpoints(css)).toEqual([]);
  });
});

describe("buildWidthMatrix", () => {
  const options = { min: 320, max: 1920, base: [320, 375, 768, 1280] };
  it("covers both sides of every threshold", () => {
    const widths = buildWidthMatrix([360, 601], options);
    for (const w of [359, 360, 361, 600, 601, 602]) expect(widths).toContain(w);
  });
  it("includes the base widths", () => {
    const widths = buildWidthMatrix([], options);
    expect(widths).toEqual([320, 375, 768, 1280]);
  });
  it("is sorted and free of duplicates", () => {
    const widths = buildWidthMatrix([375, 376], options);
    expect(widths).toEqual([...new Set(widths)].sort((a, b) => a - b));
  });
  it("stays inside the allowed range", () => {
    const widths = buildWidthMatrix([320, 1920], options);
    expect(Math.min(...widths)).toBe(320);
    expect(Math.max(...widths)).toBe(1920);
    expect(widths).not.toContain(319);
    expect(widths).not.toContain(1921);
  });
});
