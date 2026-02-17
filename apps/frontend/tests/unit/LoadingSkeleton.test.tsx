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
      expect(skeleton).toHaveStyle({
        width: "200px",
        height: "40px",
        borderRadius: "8px",
      });

      // Hidden from screen readers (decorative element)
      expect(skeleton).toHaveAttribute("aria-hidden", "true");
    });
  });

  describe("Skeleton Variants", () => {
    it("DeviceCardSkeleton renders placeholder with expected skeleton elements", () => {
      const { container } = render(<DeviceCardSkeleton />);
      expect(container.querySelector(".device-card-skeleton")).toBeInTheDocument();
      expect(container.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(2);
    });

    it("PresetSkeleton renders placeholder with expected skeleton elements", () => {
      const { container } = render(<PresetSkeleton />);
      expect(container.querySelector(".preset-skeleton")).toBeInTheDocument();
      expect(container.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(2);
    });

    it("StationCardSkeleton renders placeholder with expected skeleton elements", () => {
      const { container } = render(<StationCardSkeleton />);
      expect(container.querySelector(".station-card-skeleton")).toBeInTheDocument();
      expect(container.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(2);
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
