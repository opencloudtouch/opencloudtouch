import { describe, expect, it } from "vitest";
import { getAvatarColor, getStationInitials } from "../../src/utils/stationAvatar";

describe("stationAvatar", () => {
  describe("getStationInitials", () => {
    it("returns two initials from two-word name", () => {
      expect(getStationInitials("Radio Berlin")).toBe("RB");
    });

    it("returns two initials from multi-word name", () => {
      expect(getStationInitials("BBC World Service")).toBe("BW");
    });

    it("returns first two characters for single word", () => {
      expect(getStationInitials("SWR3")).toBe("SW");
    });

    it("returns single character for one-char name", () => {
      expect(getStationInitials("X")).toBe("X");
    });

    it("returns empty string for empty input", () => {
      expect(getStationInitials("")).toBe("");
    });

    it("handles extra whitespace", () => {
      expect(getStationInitials("  Radio   Berlin  ")).toBe("RB");
    });

    it("uppercases lowercase input", () => {
      expect(getStationInitials("jazz fm")).toBe("JF");
    });
  });

  describe("getAvatarColor", () => {
    it("returns a hex color string", () => {
      const color = getAvatarColor("Test Station");
      expect(color).toMatch(/^#[0-9A-Fa-f]{6}$/);
    });

    it("returns same color for same name (deterministic)", () => {
      expect(getAvatarColor("SWR3")).toBe(getAvatarColor("SWR3"));
    });

    it("returns different colors for different names (usually)", () => {
      const c1 = getAvatarColor("Alpha");
      const c2 = getAvatarColor("Zulu");
      // Not guaranteed but very likely for these inputs
      expect(c1).not.toBe(c2);
    });

    it("uses codePointAt and falls back gracefully for empty name", () => {
      // Empty string → hash stays 0 → picks AVATAR_COLORS[0]
      expect(getAvatarColor("")).toBe("#6264A7");
    });
  });
});
