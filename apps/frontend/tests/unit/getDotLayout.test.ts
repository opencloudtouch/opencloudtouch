/**
 * Regression test (final browser audit F1): on phones every shown device dot must be a 44px touch target.
 */
import { describe, it, expect } from "vitest";
import { getDotLayout } from "../../src/components/DeviceSwiper";

describe("getDotLayout", () => {
  it("shows all dots at full size when they fit", () => {
    expect(getDotLayout(5, 300, 44)).toEqual({ density: "full", visible: 5, pitch: 44 });
  });

  it("with the phone minimum of 44px no dot is narrower than 44px (11 devices at 184px)", () => {
    const layout = getDotLayout(11, 184, 44);
    expect(layout.density).toBe("window");
    expect(layout.visible).toBe(4);
    expect(layout.pitch).toBeGreaterThanOrEqual(44);
  });

  it("keeps every dot >= 44px for all phone widths and device counts", () => {
    for (let width = 160; width <= 600; width += 8) {
      for (let count = 1; count <= 20; count++) {
        const { pitch } = getDotLayout(count, width, 44);
        expect(pitch, `count=${count} width=${width}`).toBeGreaterThanOrEqual(width >= 3 * 44 ? 44 : 0);
      }
    }
  });

  it("keeps the denser layout above phone width (min 24px)", () => {
    const layout = getDotLayout(11, 184, 24);
    expect(layout.density).toBe("window");
    expect(layout.visible).toBe(7);
  });

  it("uses the dense layout when the dots fit at the minimum size", () => {
    const layout = getDotLayout(6, 200, 24);
    expect(layout.density).toBe("dense");
    expect(layout.pitch).toBeCloseTo(33.3, 1);
  });
});
