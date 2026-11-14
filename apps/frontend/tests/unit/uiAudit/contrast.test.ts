import { describe, it, expect } from "vitest";
import {
  parseCssColor,
  compositeOver,
  relativeLuminance,
  contrastRatio,
  requiredRatio,
  flattenLayers,
  evaluateContrast,
} from "../../e2e/support/uiAudit/contrast";

const white = { r: 255, g: 255, b: 255, a: 1 };
const black = { r: 0, g: 0, b: 0, a: 1 };

describe("parseCssColor", () => {
  it("parses rgb() and rgba()", () => {
    expect(parseCssColor("rgb(255, 0, 10)")).toEqual({ r: 255, g: 0, b: 10, a: 1 });
    expect(parseCssColor("rgba(0, 0, 0, 0.5)")).toEqual({ r: 0, g: 0, b: 0, a: 0.5 });
  });
  it("parses the space separated syntax with a slash alpha", () => {
    expect(parseCssColor("rgb(10 20 30 / 50%)")).toEqual({ r: 10, g: 20, b: 30, a: 0.5 });
    expect(parseCssColor("rgb(10 20 30 / 0.25)")).toEqual({ r: 10, g: 20, b: 30, a: 0.25 });
  });
  it("parses hex in 3, 6 and 8 digits", () => {
    expect(parseCssColor("#fff")).toEqual(white);
    expect(parseCssColor("#1a1a1a")).toEqual({ r: 26, g: 26, b: 26, a: 1 });
    const half = parseCssColor("#ffffff80");
    expect(half?.a).toBeCloseTo(0.502, 2);
  });
  it("parses transparent and the color(srgb) form Chrome can return", () => {
    expect(parseCssColor("transparent")).toEqual({ r: 0, g: 0, b: 0, a: 0 });
    expect(parseCssColor("color(srgb 1 0 0 / 0.5)")).toEqual({ r: 255, g: 0, b: 0, a: 0.5 });
    expect(parseCssColor("color(srgb 0 0.5 1)")).toEqual({ r: 0, g: 128, b: 255, a: 1 });
  });
  it("returns null for things it cannot resolve", () => {
    expect(parseCssColor("")).toBeNull();
    expect(parseCssColor("var(--x)")).toBeNull();
    expect(parseCssColor("oklch(0.5 0.1 200)")).toBeNull();
    expect(parseCssColor("#12")).toBeNull();
  });
});

describe("compositeOver", () => {
  it("blends a translucent colour over an opaque one", () => {
    expect(compositeOver({ ...white, a: 0.5 }, black)).toEqual({ r: 128, g: 128, b: 128, a: 1 });
  });
  it("keeps an opaque colour and drops a fully transparent one", () => {
    expect(compositeOver(white, black)).toEqual(white);
    expect(compositeOver({ ...white, a: 0 }, black)).toEqual(black);
  });
});

describe("relativeLuminance and contrastRatio", () => {
  it("has the WCAG anchors", () => {
    expect(relativeLuminance(white)).toBeCloseTo(1, 5);
    expect(relativeLuminance(black)).toBeCloseTo(0, 5);
    expect(relativeLuminance({ r: 128, g: 128, b: 128, a: 1 })).toBeCloseTo(0.2159, 3);
  });
  it("gives 21:1 for black on white, 1:1 for equal colours, and is symmetric", () => {
    expect(contrastRatio(black, white)).toBeCloseTo(21, 5);
    expect(contrastRatio(white, black)).toBeCloseTo(21, 5);
    expect(contrastRatio(white, white)).toBeCloseTo(1, 5);
  });
  it("matches a known reference value: #767676 on white is 4.54:1", () => {
    expect(contrastRatio({ r: 0x76, g: 0x76, b: 0x76, a: 1 }, white)).toBeCloseTo(4.54, 2);
  });
});

describe("requiredRatio", () => {
  it("needs 4.5:1 for normal text", () => {
    expect(requiredRatio(16, 400)).toBe(4.5);
    expect(requiredRatio(14, 700)).toBe(4.5);
    expect(requiredRatio(18.6, 700)).toBe(4.5);
  });
  it("needs 3:1 for large text: 24px, or 18.66px and bold", () => {
    expect(requiredRatio(24, 400)).toBe(3);
    expect(requiredRatio(18.66, 700)).toBe(3);
    expect(requiredRatio(18.66, 400)).toBe(4.5);
  });
});

describe("flattenLayers", () => {
  it("returns the first opaque layer", () => {
    expect(flattenLayers([white, black], black)).toEqual(white);
  });
  it("composites translucent layers over the next ones, innermost first", () => {
    const tint = { r: 255, g: 0, b: 0, a: 0.5 };
    expect(flattenLayers([tint, white], black)).toEqual({ r: 255, g: 128, b: 128, a: 1 });
  });
  it("falls back to the page colour when every layer is transparent", () => {
    expect(flattenLayers([{ ...white, a: 0 }], black)).toEqual(black);
    expect(flattenLayers([], white)).toEqual(white);
  });
});

describe("evaluateContrast", () => {
  const base = { backgrounds: [white], pageBackground: white, fontSizePx: 16, fontWeight: 400 };
  it("passes dark text on white", () => {
    const r = evaluateContrast({ ...base, color: { r: 20, g: 23, b: 28, a: 1 } });
    expect(r.pass).toBe(true);
    expect(r.required).toBe(4.5);
    expect(r.ratio).toBeGreaterThan(15);
  });
  it("fails pale text on white", () => {
    const r = evaluateContrast({ ...base, color: { r: 200, g: 200, b: 200, a: 1 } });
    expect(r.pass).toBe(false);
    expect(r.ratio).toBeLessThan(2);
  });
  it("uses the large-text threshold", () => {
    const grey = { r: 140, g: 140, b: 140, a: 1 }; // about 3.4:1 on white
    expect(evaluateContrast({ ...base, color: grey }).pass).toBe(false);
    expect(evaluateContrast({ ...base, color: grey, fontSizePx: 24 }).pass).toBe(true);
  });
  it("blends translucent text and element opacity over the background", () => {
    const opaque = evaluateContrast({ ...base, color: black });
    const faded = evaluateContrast({ ...base, color: black, opacity: 0.5 });
    expect(faded.ratio).toBeLessThan(opaque.ratio);
    const alphaText = evaluateContrast({ ...base, color: { ...black, a: 0.5 } });
    expect(alphaText.ratio).toBeCloseTo(faded.ratio, 5);
  });
});
