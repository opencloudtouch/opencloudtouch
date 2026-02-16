import { describe, it, expect, beforeEach } from "vitest";
import {
  getDeviceImage,
  getAllDeviceImages,
  preloadDeviceImages,
  getDeviceDisplayName,
  getDeviceAspectRatio,
} from "./deviceImages";

describe("deviceImages utilities", () => {
  describe("getDeviceImage", () => {
    it("should return ST10 image for SoundTouch 10", () => {
      expect(getDeviceImage("SoundTouch 10")).toBe("/images/devices/st10.svg");
      expect(getDeviceImage("soundtouch 10")).toBe("/images/devices/st10.svg");
      expect(getDeviceImage("ST 10")).toBe("/images/devices/st10.svg");
    });

    it("should return ST20 image for SoundTouch 20", () => {
      expect(getDeviceImage("SoundTouch 20")).toBe("/images/devices/st20.svg");
      expect(getDeviceImage("ST20")).toBe("/images/devices/st20.svg");
    });

    it("should return ST30 image for SoundTouch 30", () => {
      expect(getDeviceImage("SoundTouch 30")).toBe("/images/devices/st30.svg");
      expect(getDeviceImage("ST 30")).toBe("/images/devices/st30.svg");
    });

    it("should return ST300 image for SoundTouch 300", () => {
      expect(getDeviceImage("SoundTouch 300")).toBe("/images/devices/st300.svg");
      expect(getDeviceImage("ST300")).toBe("/images/devices/st300.svg");
    });

    it("should NOT confuse ST30 with ST300", () => {
      expect(getDeviceImage("ST30")).toBe("/images/devices/st30.svg");
      expect(getDeviceImage("ST300")).toBe("/images/devices/st300.svg");
      expect(getDeviceImage("SoundTouch 30")).not.toBe("/images/devices/st300.svg");
    });

    it("should return default image for unknown models", () => {
      expect(getDeviceImage("Unknown Model")).toBe("/images/devices/default.svg");
      expect(getDeviceImage("Wave Music System")).toBe("/images/devices/default.svg");
      expect(getDeviceImage("")).toBe("/images/devices/default.svg");
      expect(getDeviceImage(null)).toBe("/images/devices/default.svg");
      expect(getDeviceImage(undefined)).toBe("/images/devices/default.svg");
    });
  });

  describe("getAllDeviceImages", () => {
    it("should return all device image paths", () => {
      const images = getAllDeviceImages();
      expect(images).toHaveProperty("st10");
      expect(images).toHaveProperty("st20");
      expect(images).toHaveProperty("st30");
      expect(images).toHaveProperty("st300");
      expect(images).toHaveProperty("default");
      expect(Object.keys(images)).toHaveLength(5);
    });
  });

  describe("preloadDeviceImages", () => {
    beforeEach(() => {
      // Mock the Image constructor
      global.Image = class {
        public src = "";
        constructor() {
          // Simulate image loading
        }
      } as unknown as typeof Image;
    });

    it("should attempt to preload all device images", () => {
      const imageSrcList: string[] = [];

      // Override Image to track src assignments
      global.Image = class {
        private _src = "";

        get src() {
          return this._src;
        }

        set src(value: string) {
          this._src = value;
          imageSrcList.push(value);
        }
      } as unknown as typeof Image;

      preloadDeviceImages();

      // Should create images for all device types
      expect(imageSrcList).toContain("/images/devices/st10.svg");
      expect(imageSrcList).toContain("/images/devices/st20.svg");
      expect(imageSrcList).toContain("/images/devices/st30.svg");
      expect(imageSrcList).toContain("/images/devices/st300.svg");
      expect(imageSrcList).toContain("/images/devices/default.svg");
      expect(imageSrcList).toHaveLength(5);
    });

    it("should not throw errors when called", () => {
      expect(() => preloadDeviceImages()).not.toThrow();
    });
  });

  describe("getDeviceDisplayName", () => {
    it("should format display names correctly", () => {
      expect(getDeviceDisplayName("SoundTouch 10")).toBe("SoundTouch 10");
      expect(getDeviceDisplayName("ST20")).toBe("SoundTouch 20");
      expect(getDeviceDisplayName("st 30")).toBe("SoundTouch 30");
      expect(getDeviceDisplayName("ST300")).toBe("SoundTouch 300");
    });

    it("should return original name for unknown models", () => {
      expect(getDeviceDisplayName("Wave System IV")).toBe("Wave System IV");
      expect(getDeviceDisplayName("Unknown")).toBe("Unknown");
    });

    it("should handle empty input gracefully", () => {
      expect(getDeviceDisplayName("")).toBe("Unknown Device");
      expect(getDeviceDisplayName(null)).toBe("Unknown Device");
      expect(getDeviceDisplayName(undefined)).toBe("Unknown Device");
    });
  });

  describe("getDeviceAspectRatio", () => {
    it("should return correct aspect ratio classes", () => {
      expect(getDeviceAspectRatio("SoundTouch 10")).toBe("aspect-square");
      expect(getDeviceAspectRatio("SoundTouch 20")).toBe("aspect-[3/2]");
      expect(getDeviceAspectRatio("SoundTouch 30")).toBe("aspect-[14/9]");
      expect(getDeviceAspectRatio("SoundTouch 300")).toBe("aspect-[4/1]");
    });

    it("should return default for unknown models", () => {
      expect(getDeviceAspectRatio("Unknown")).toBe("aspect-square");
      expect(getDeviceAspectRatio("")).toBe("aspect-square");
      expect(getDeviceAspectRatio(null)).toBe("aspect-square");
    });
  });
});
