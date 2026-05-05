import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import CloudBadge from "../../src/components/CloudBadge";

describe("CloudBadge Component", () => {
  describe("Default behavior (HAS_EXT_RESOLVER=true)", () => {
    it("should render compatible badge when not cloud-dependent", () => {
      const { container } = render(
        <CloudBadge isCloudDependent={false} />
      );

      expect(container.querySelector(".cloud-badge.compatible")).toBeInTheDocument();
    });

    it("should render dependent badge for TUNEIN source", () => {
      const { container } = render(
        <CloudBadge isCloudDependent={true} source="TUNEIN" />
      );

      expect(container.querySelector(".cloud-badge.dependent")).toBeInTheDocument();
    });

    it("should render dependent badge for non-TUNEIN cloud-dependent source", () => {
      const { container } = render(
        <CloudBadge isCloudDependent={true} source="OTHER" />
      );

      expect(container.querySelector(".cloud-badge.dependent")).toBeInTheDocument();
    });
  });

  describe("Feature Toggle (HAS_EXT_RESOLVER=false)", () => {
    it("should render nothing for TUNEIN cloud-dependent source when flag is false", async () => {
      vi.resetModules();
      vi.doMock("../../src/config/capabilities", () => ({ HAS_EXT_RESOLVER: false }));
      const { default: CloudBadgeGated } = await import("../../src/components/CloudBadge");

      const { container } = render(
        <CloudBadgeGated isCloudDependent={true} source="TUNEIN" />
      );

      expect(container.querySelector(".cloud-badge")).not.toBeInTheDocument();
      expect(container.innerHTML).toBe("");

      vi.doUnmock("../../src/config/capabilities");
    });

    it("should still render compatible badge when flag is false and not cloud-dependent", async () => {
      vi.resetModules();
      vi.doMock("../../src/config/capabilities", () => ({ HAS_EXT_RESOLVER: false }));
      const { default: CloudBadgeGated } = await import("../../src/components/CloudBadge");

      const { container } = render(
        <CloudBadgeGated isCloudDependent={false} />
      );

      expect(container.querySelector(".cloud-badge.compatible")).toBeInTheDocument();

      vi.doUnmock("../../src/config/capabilities");
    });

    it("should still render dependent badge for non-TUNEIN source when flag is false", async () => {
      vi.resetModules();
      vi.doMock("../../src/config/capabilities", () => ({ HAS_EXT_RESOLVER: false }));
      const { default: CloudBadgeGated } = await import("../../src/components/CloudBadge");

      const { container } = render(
        <CloudBadgeGated isCloudDependent={true} source="OTHER" />
      );

      expect(container.querySelector(".cloud-badge.dependent")).toBeInTheDocument();

      vi.doUnmock("../../src/config/capabilities");
    });
  });
});
