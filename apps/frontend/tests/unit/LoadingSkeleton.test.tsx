/**
 * LoadingSkeleton Component Tests
 *
 * User Story: Als User sehe ich Platzhalter während Inhalte laden
 *
 * Focus: Skeleton components render correctly with configurable dimensions
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import {
  Skeleton,
  DeviceCardSkeleton,
  PresetSkeleton,
  StationCardSkeleton,
  SkeletonList,
} from "../../src/components/LoadingSkeleton";

describe("LoadingSkeleton", () => {
  describe("Skeleton Base Component", () => {
    it("renders with configurable dimensions", () => {
      const { container, rerender } = render(<Skeleton />);
      const skeleton = container.querySelector(".skeleton");

      // Default dimensions
      expect(skeleton).toBeInTheDocument();
      expect(skeleton).toHaveStyle({ width: "100%", height: "20px" });

      // Custom dimensions
      rerender(<Skeleton width="200px" height="40px" borderRadius="8px" />);
      const skeleton2 = container.querySelector(".skeleton") as HTMLElement;
      expect(skeleton2).toHaveStyle({ width: "200px", height: "40px" });
      // border-radius is a CSS shorthand — getComputedStyle in jsdom does not
      // resolve it, so we check the inline style directly.
      expect(skeleton2.style.borderRadius).toBe("8px");

      // Hidden from screen readers (decorative element)
      expect(skeleton).toHaveAttribute("aria-hidden", "true");
    });
  });

  describe("SkeletonList", () => {
    it("renders configurable number of skeleton items", () => {
      const { container, rerender } = render(
        <SkeletonList count={5} SkeletonComponent={DeviceCardSkeleton} />
      );
      expect(container.querySelectorAll(".device-card-skeleton")).toHaveLength(5);

      rerender(<SkeletonList count={3} SkeletonComponent={PresetSkeleton} />);
      expect(container.querySelectorAll(".preset-skeleton")).toHaveLength(3);

      rerender(<SkeletonList count={2} SkeletonComponent={StationCardSkeleton} />);
      expect(container.querySelectorAll(".station-card-skeleton")).toHaveLength(2);
    });
  });
});
