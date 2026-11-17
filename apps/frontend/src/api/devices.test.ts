import { describe, it, expect } from "vitest";
import { toRepeatMode, toShuffleMode } from "./devices";

describe("toShuffleMode", () => {
  it("maps speaker values to ShuffleMode", () => {
    expect(toShuffleMode("SHUFFLE_ON")).toBe("on");
    expect(toShuffleMode("SHUFFLE_OFF")).toBe("off");
  });

  it("returns null for missing or unknown values", () => {
    expect(toShuffleMode(null)).toBeNull();
    expect(toShuffleMode(undefined)).toBeNull();
    expect(toShuffleMode("REPEAT_ALL")).toBeNull();
  });
});

describe("toRepeatMode", () => {
  it("maps speaker values to RepeatMode", () => {
    expect(toRepeatMode("REPEAT_OFF")).toBe("off");
    expect(toRepeatMode("REPEAT_ALL")).toBe("all");
    expect(toRepeatMode("REPEAT_ONE")).toBe("one");
  });

  it("returns null for missing or unknown values", () => {
    expect(toRepeatMode(null)).toBeNull();
    expect(toRepeatMode("SHUFFLE_ON")).toBeNull();
  });
});
