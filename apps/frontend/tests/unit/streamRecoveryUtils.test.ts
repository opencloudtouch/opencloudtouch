import { describe, it, expect } from "vitest";
import {
  isDirty,
  minutesToSeconds,
  parseAttempts,
  parseMinutes,
  secondsToMinutes,
  splitPlayTime,
} from "../../src/utils/streamRecovery";

describe("minutes <-> seconds", () => {
  it("converts both ways", () => {
    expect(minutesToSeconds(10)).toBe(600);
    expect(secondsToMinutes(600)).toBe(10);
    expect(secondsToMinutes(86400)).toBe(1440);
  });
});

describe("parseMinutes", () => {
  it.each([
    ["1", 1],
    ["10", 10],
    ["1440", 1440],
    [" 30 ", 30],
  ])("accepts %s", (text, value) => {
    expect(parseMinutes(text)).toBe(value);
  });

  it.each(["", "0", "1441", "-5", "1.5", "1e2", "abc", "10 min"])("rejects %j", (text) => {
    expect(parseMinutes(text)).toBeNull();
  });
});

describe("parseAttempts", () => {
  it.each([
    ["1", 1],
    ["3", 3],
    ["10", 10],
  ])("accepts %s", (text, value) => {
    expect(parseAttempts(text)).toBe(value);
  });

  it.each(["", "0", "11", "2.5", "x"])("rejects %j", (text) => {
    expect(parseAttempts(text)).toBeNull();
  });
});

describe("isDirty", () => {
  const baseline = { enabled: false, minutes: "10", attempts: "3" };

  it("is false for an identical form, also with numerically equal text", () => {
    expect(isDirty({ ...baseline }, baseline)).toBe(false);
    expect(isDirty({ ...baseline, minutes: "010" }, baseline)).toBe(false);
  });

  it("is true when any field changes", () => {
    expect(isDirty({ ...baseline, enabled: true }, baseline)).toBe(true);
    expect(isDirty({ ...baseline, minutes: "11" }, baseline)).toBe(true);
    expect(isDirty({ ...baseline, attempts: "4" }, baseline)).toBe(true);
  });

  it("treats unparsable text as a change", () => {
    expect(isDirty({ ...baseline, minutes: "" }, baseline)).toBe(true);
    expect(isDirty({ ...baseline, attempts: "x" }, baseline)).toBe(true);
  });
});

describe("splitPlayTime", () => {
  it("splits seconds into hours and minutes", () => {
    expect(splitPlayTime(21600)).toEqual({ hours: 6, minutes: 0 });
    expect(splitPlayTime(5400)).toEqual({ hours: 1, minutes: 30 });
    expect(splitPlayTime(59)).toEqual({ hours: 0, minutes: 0 });
  });
});
