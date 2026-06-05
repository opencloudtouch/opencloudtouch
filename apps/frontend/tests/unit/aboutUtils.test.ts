import { describe, it, expect, vi } from "vitest";
import {
  parseCSVLine,
  getRandomThankYou,
  getFontSize,
  generateGradientColor,
  cleanName,
} from "../../src/pages/aboutUtils";
import type { Supporter } from "../../src/pages/aboutUtils";

describe("parseCSVLine", () => {
  it("parses simple unquoted fields", () => {
    expect(parseCSVLine("Alice,monthly,50,10,2024-01-15")).toEqual([
      "Alice",
      "monthly",
      "50",
      "10",
      "2024-01-15",
    ]);
  });

  it("parses quoted fields with commas", () => {
    expect(parseCSVLine('"Smith, John",one-time,25,0,2024-03-01')).toEqual([
      "Smith, John",
      "one-time",
      "25",
      "0",
      "2024-03-01",
    ]);
  });

  it("parses quoted fields with escaped quotes", () => {
    expect(parseCSVLine('"He said ""hello""",one-time,10,0,2024-05-01')).toEqual([
      'He said "hello"',
      "one-time",
      "10",
      "0",
      "2024-05-01",
    ]);
  });

  it("handles empty fields", () => {
    expect(parseCSVLine(",,,")).toEqual(["", "", "", ""]);
  });

  it("trims whitespace in unquoted fields", () => {
    expect(parseCSVLine("  Alice  , monthly , 50 ")).toEqual(["Alice", "monthly", "50"]);
  });

  it("handles single field", () => {
    expect(parseCSVLine("Alice")).toEqual(["Alice"]);
  });

  it("handles empty line", () => {
    expect(parseCSVLine("")).toEqual([""]);
  });
});

describe("getRandomThankYou", () => {
  it("returns a string for regular supporter in English", () => {
    const result = getRandomThankYou(false, "en");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("returns a string for monthly supporter in English", () => {
    const result = getRandomThankYou(true, "en");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("falls back to English for unknown language", () => {
    const result = getRandomThankYou(false, "xx");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("handles language with region code", () => {
    const result = getRandomThankYou(false, "en-US");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("returns German phrases for de", () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    const result = getRandomThankYou(false, "de");
    expect(result).toBe("Danke für deine Unterstützung! ☕");
    vi.restoreAllMocks();
  });

  it("returns monthly phrases when isMonthly is true", () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    const result = getRandomThankYou(true, "en");
    expect(result).toBe("You're a champion! 🏆💛");
    vi.restoreAllMocks();
  });
});

describe("getFontSize", () => {
  const makeSupporter = (amount: number, monthlyAmount: number): Supporter => ({
    name: "Test",
    type: "one-time",
    amount,
    monthlyAmount,
    firstSupportDate: "2024-01-01",
  });

  it("returns minimum size for zero support", () => {
    const result = getFontSize(makeSupporter(0, 0), 100);
    expect(result).toBe(12);
  });

  it("returns maximum size for max support", () => {
    const result = getFontSize(makeSupporter(100, 0), 100);
    expect(result).toBe(32);
  });

  it("returns intermediate size for partial support", () => {
    const result = getFontSize(makeSupporter(50, 0), 100);
    expect(result).toBeGreaterThan(12);
    expect(result).toBeLessThan(32);
  });

  it("combines amount and monthlyAmount", () => {
    const result = getFontSize(makeSupporter(30, 20), 100);
    const resultSingleField = getFontSize(makeSupporter(50, 0), 100);
    expect(result).toBe(resultSingleField);
  });
});

describe("generateGradientColor", () => {
  it("returns an HSL color string", () => {
    const result = generateGradientColor(0, 10);
    expect(result).toMatch(/^hsl\(\d+, \d+%, \d+%\)$/);
  });

  it("generates different colors for different indices", () => {
    const color1 = generateGradientColor(0, 10);
    const color2 = generateGradientColor(5, 10);
    expect(color1).not.toBe(color2);
  });

  it("wraps hue around 360 degrees", () => {
    const result = generateGradientColor(10, 10);
    expect(result).toMatch(/^hsl\(360, \d+%, \d+%\)$/);
  });
});

describe("cleanName", () => {
  it("converts GitHub URL to @username", () => {
    expect(cleanName("https://github.com/testuser")).toBe("@testuser");
  });

  it("leaves non-GitHub names unchanged", () => {
    expect(cleanName("Alice")).toBe("Alice");
  });

  it("handles GitHub URL with path", () => {
    expect(cleanName("https://github.com/org/repo")).toBe("@org/repo");
  });

  it("handles empty string", () => {
    expect(cleanName("")).toBe("");
  });
});
