/**
 * LoadingSkeleton Component Tests
 * Tests for loading placeholder components
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
  describe("Skeleton", () => {
    it("renders with default dimensions", () => {
      const { container } = render(<Skeleton />);
      const skeleton = container.querySelector(".skeleton");

      expect(skeleton).toBeInTheDocument();
      expect(skeleton).toHaveStyle({ width: "100%", height: "20px" });
    });

    it("renders with custom dimensions", () => {
      const { container } = render(<Skeleton width="200px" height="40px" borderRadius="8px" />);
      const skeleton = container.querySelector(".skeleton");

      expect(skeleton).toHaveStyle({
        width: "200px",
        height: "40px",
        borderRadius: "8px",
      });
    });

    it("has aria-hidden attribute for accessibility", () => {
      const { container } = render(<Skeleton />);
      const skeleton = container.querySelector(".skeleton");

      expect(skeleton).toHaveAttribute("aria-hidden", "true");
    });

    it("applies custom className", () => {
      const { container } = render(<Skeleton className="custom-skeleton" />);
      const skeleton = container.querySelector(".skeleton");

      expect(skeleton).toHaveClass("skeleton");
      expect(skeleton).toHaveClass("custom-skeleton");
    });
  });

  describe("DeviceCardSkeleton", () => {
    it("renders device card placeholder structure", () => {
      const { container } = render(<DeviceCardSkeleton />);

      expect(container.querySelector(".device-card-skeleton")).toBeInTheDocument();
      expect(container.querySelector(".device-card-skeleton-content")).toBeInTheDocument();
      expect(container.querySelectorAll(".skeleton")).toHaveLength(3); // Icon + 2 text lines
    });
  });

  describe("PresetSkeleton", () => {
    it("renders preset placeholder structure", () => {
      const { container } = render(<PresetSkeleton />);

      expect(container.querySelector(".preset-skeleton")).toBeInTheDocument();
      expect(container.querySelector(".preset-skeleton-content")).toBeInTheDocument();
      expect(container.querySelectorAll(".skeleton")).toHaveLength(3); // Icon + 2 text lines
    });
  });

  describe("StationCardSkeleton", () => {
    it("renders station card placeholder structure", () => {
      const { container } = render(<StationCardSkeleton />);

      expect(container.querySelector(".station-card-skeleton")).toBeInTheDocument();
      expect(container.querySelector(".station-card-skeleton-content")).toBeInTheDocument();
      expect(container.querySelectorAll(".skeleton")).toHaveLength(3); // Image + 2 text lines
    });
  });

  describe("SkeletonList", () => {
    it("renders multiple skeleton items", () => {
      const { container } = render(
        <SkeletonList count={5} SkeletonComponent={DeviceCardSkeleton} />
      );

      const skeletons = container.querySelectorAll(".device-card-skeleton");
      expect(skeletons).toHaveLength(5);
    });

    it("renders correct number of items", () => {
      const { container } = render(<SkeletonList count={3} SkeletonComponent={PresetSkeleton} />);

      const skeletons = container.querySelectorAll(".preset-skeleton");
      expect(skeletons).toHaveLength(3);
    });

    it("renders with different skeleton types", () => {
      const { container } = render(
        <SkeletonList count={2} SkeletonComponent={StationCardSkeleton} />
      );

      const skeletons = container.querySelectorAll(".station-card-skeleton");
      expect(skeletons).toHaveLength(2);
    });
  });
});
