import { afterEach, describe, expect, it, vi } from "vitest";
import {
  STORAGE_KEY,
  clampFade,
  clockOffsetMs,
  derivePhase,
  formatCountdown,
  isFadeAllowed,
  loadDefaults,
  parseDuration,
  remainingMs,
  saveDefaults,
} from "../../src/utils/sleepTimer";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("parseDuration", () => {
  it.each([
    ["1", 1],
    ["30", 30],
    ["720", 720],
    [" 45 ", 45],
  ])("accepts %s", (text, value) => {
    expect(parseDuration(text)).toBe(value);
  });

  it.each(["", "0", "721", "-1", "1.5", "abc", "1e2", "30 min"])("rejects %j", (text) => {
    expect(parseDuration(text)).toBeNull();
  });
});

describe("fade rules", () => {
  it("allows a fade up to the duration", () => {
    expect(isFadeAllowed(60, 1)).toBe(true);
    expect(isFadeAllowed(90, 1)).toBe(false);
    expect(isFadeAllowed(0, 1)).toBe(true);
  });

  it("clamps to the longest offered fade that fits", () => {
    expect(clampFade(60, 1)).toBe(60);
    expect(clampFade(30, 1)).toBe(30);
    // synthetic: a 10 s offer cannot exceed a duration shorter than the option
    expect(clampFade(60, 0.5)).toBe(30);
    expect(clampFade(60, 0.1)).toBe(0);
  });
});

describe("countdown", () => {
  it("formats m:ss below one hour and h:mm:ss otherwise", () => {
    expect(formatCountdown(0)).toBe("0:00");
    expect(formatCountdown(59_000)).toBe("0:59");
    expect(formatCountdown(61_000)).toBe("1:01");
    expect(formatCountdown(59 * 60_000 + 59_000)).toBe("59:59");
    expect(formatCountdown(3_600_000)).toBe("1:00:00");
    expect(formatCountdown(2 * 3_600_000 + 3 * 60_000 + 4_000)).toBe("2:03:04");
  });

  it("never shows a negative time and rounds partial seconds up", () => {
    expect(formatCountdown(-5000)).toBe("0:00");
    expect(formatCountdown(1)).toBe("0:01");
  });

  it("measures against the server clock, whatever this device's clock says", () => {
    const serverNow = Date.parse("2026-10-26T12:00:00Z");
    const deviceNow = serverNow + 5 * 60_000; // this device is 5 minutes ahead
    const offset = clockOffsetMs("2026-10-26T12:00:00Z", deviceNow);
    expect(offset).toBe(-5 * 60_000);
    expect(remainingMs("2026-10-26T12:30:00Z", offset, deviceNow)).toBe(30 * 60_000);
    expect(remainingMs("2026-10-26T12:30:00Z", offset, deviceNow + 10_000)).toBe(
      30 * 60_000 - 10_000
    );
  });
});

describe("derivePhase", () => {
  const endsAt = "2026-10-26T12:30:00Z";
  const at = (secondsBeforeEnd: number) => Date.parse(endsAt) - secondsBeforeEnd * 1000;

  it("is running before the fade, fading inside it and ending at 0", () => {
    expect(derivePhase(endsAt, 30, 0, at(600))).toBe("running");
    expect(derivePhase(endsAt, 30, 0, at(31))).toBe("running");
    expect(derivePhase(endsAt, 30, 0, at(30))).toBe("fading");
    expect(derivePhase(endsAt, 30, 0, at(1))).toBe("fading");
    expect(derivePhase(endsAt, 30, 0, at(0))).toBe("ending");
    expect(derivePhase(endsAt, 30, 0, at(-5))).toBe("ending");
  });

  it("never fades without a fade", () => {
    expect(derivePhase(endsAt, 0, 0, at(5))).toBe("running");
  });
});

describe("remembered defaults", () => {
  it("falls back to 30 min / 30 s / stop", () => {
    expect(loadDefaults()).toEqual({ duration: 30, fade: 30, endAction: "stop" });
  });

  it("round-trips valid values", () => {
    saveDefaults({ duration: 45, fade: 10, endAction: "standby" });
    expect(loadDefaults()).toEqual({ duration: 45, fade: 10, endAction: "standby" });
  });

  it("validates restored values", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ duration: 5000, fade: 7, endAction: "explode" })
    );
    expect(loadDefaults()).toEqual({ duration: 30, fade: 30, endAction: "stop" });
  });

  it("clamps a fade larger than the duration", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ duration: 0, fade: 60, endAction: "stop" }));
    // duration 0 is invalid -> default 30 min, fade 60 fits
    expect(loadDefaults().duration).toBe(30);
    expect(loadDefaults().fade).toBe(60);
  });

  it("ignores corrupt JSON", () => {
    localStorage.setItem(STORAGE_KEY, "{nope");
    expect(loadDefaults()).toEqual({ duration: 30, fade: 30, endAction: "stop" });
  });

  it("works when storage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(loadDefaults()).toEqual({ duration: 30, fade: 30, endAction: "stop" });
    expect(() => saveDefaults({ duration: 15, fade: 0, endAction: "stop" })).not.toThrow();
  });
});
