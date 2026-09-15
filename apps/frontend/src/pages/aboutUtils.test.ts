/**
 * Tests for aboutUtils.ts
 *
 * Focus: cleanName() — hides everything after an "@" unless the "@"
 * is the very first character (i.e. a handle like "@Struppie").
 */

import { describe, it, expect } from "vitest";
import { cleanName, parseCSVLine, getFontSize, generateGradientColor } from "./aboutUtils";

describe("cleanName", () => {
  it("leaves plain names untouched", () => {
    expect(cleanName("Simon")).toBe("Simon");
    expect(cleanName("Peter St.")).toBe("Peter St.");
  });

  it("keeps a leading @ handle fully intact", () => {
    expect(cleanName("@Struppie")).toBe("@Struppie");
    expect(cleanName("@Eisenvater")).toBe("@Eisenvater");
  });

  it("strips everything from an email address's @ onward", () => {
    expect(cleanName("sebasscholz@climatejustice.social")).toBe("sebasscholz");
  });

  it("strips everything from the first @ onward when it's not at position 0", () => {
    expect(cleanName("MASTODON: @nightwatch2359@social.tchncs.de")).toBe("MASTODON:");
  });

  it("trims trailing whitespace left behind after stripping", () => {
    expect(cleanName("Name @handle")).toBe("Name");
  });

  it("returns the name unchanged when there is no @ at all", () => {
    expect(cleanName("Jürgen N.")).toBe("Jürgen N.");
    expect(cleanName("")).toBe("");
  });

  it("still converts GitHub profile URLs to @handles (existing behavior)", () => {
    expect(cleanName("https://github.com/Zimbo88")).toBe("@Zimbo88");
  });

  it("does not run the @ email at github handle through the @-stripping branch", () => {
    // GitHub URL branch takes priority and produces "@Zimbo88";
    // the leading "@" there must NOT be treated as a reason to strip further.
    expect(cleanName("https://github.com/Zimbo88")).not.toBe("");
  });
});

// Sanity checks that these existing helpers still work — kept minimal since
// they're not the subject of this change but share the file.
describe("aboutUtils (existing helpers, regression guard)", () => {
  it("parseCSVLine splits a simple line", () => {
    expect(parseCSVLine("Simon,one-time,10,0,2024-01-01")).toEqual([
      "Simon",
      "one-time",
      "10",
      "0",
      "2024-01-01",
    ]);
  });

  it("getFontSize scales between 12 and 32", () => {
    const supporter = {
      name: "x",
      type: "one-time" as const,
      amount: 10,
      monthlyAmount: 0,
      firstSupportDate: "",
    };
    const size = getFontSize(supporter, 10);
    expect(size).toBeGreaterThanOrEqual(12);
    expect(size).toBeLessThanOrEqual(32);
  });

  it("generateGradientColor returns an hsl string", () => {
    expect(generateGradientColor(0, 5)).toMatch(/^hsl\(/);
  });
});
