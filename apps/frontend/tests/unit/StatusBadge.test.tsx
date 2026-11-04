import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusBadge from "../../src/components/StatusBadge";
import type { SetupStatus } from "../../src/api/setup";

describe("StatusBadge", () => {
  const ALL_STATUSES: SetupStatus[] = [
    "unconfigured",
    "pending",
    "configured",
    "failed",
    "outdated",
    "offline",
    "unknown",
  ];

  const EXPECTED_LABELS: Record<SetupStatus, string> = {
    unconfigured: "Not configured",
    pending: "Setup in progress...",
    configured: "Configured",
    failed: "Failed",
    outdated: "Outdated",
    offline: "Offline",
    unknown: "Unknown",
  };

  const EXPECTED_VARIANTS: Record<SetupStatus, string> = {
    unconfigured: "warning",
    pending: "info",
    configured: "success",
    failed: "danger",
    outdated: "warning",
    offline: "neutral",
    unknown: "neutral",
  };

  describe("Rendering", () => {
    it.each(ALL_STATUSES)("renders an icon with an accessible name for '%s' status", (status) => {
      const { container } = render(<StatusBadge status={status} />);
      const icon = screen.getByRole("img", { name: EXPECTED_LABELS[status] });
      expect(icon).toBeInTheDocument();
      expect(icon.querySelector("svg")).not.toBeNull();
      expect(container.querySelector(".ui-badge--icon")).not.toBeNull();
    });

    it("does not show label by default", () => {
      render(<StatusBadge status="configured" />);
      expect(screen.queryByText("Configured")).not.toBeInTheDocument();
    });

    it("shows label when showLabel is true", () => {
      render(<StatusBadge status="configured" showLabel />);
      expect(screen.getByText("Configured")).toBeInTheDocument();
      // With a visible label the icon is decorative
      expect(screen.queryByRole("img")).not.toBeInTheDocument();
    });
  });

  describe("Status Labels", () => {
    it.each(Object.entries(EXPECTED_LABELS))(
      "shows correct label for '%s'",
      (status, expectedLabel) => {
        render(<StatusBadge status={status as SetupStatus} showLabel />);
        expect(screen.getByText(expectedLabel)).toBeInTheDocument();
      },
    );
  });

  describe("CSS Classes", () => {
    it.each(Object.entries(EXPECTED_VARIANTS))(
      "applies the variant class for '%s'",
      (status, variant) => {
        const { container } = render(<StatusBadge status={status as SetupStatus} />);
        expect(container.firstChild).toHaveClass("ui-badge", `ui-badge--${variant}`);
      },
    );

    it("applies medium size by default", () => {
      const { container } = render(<StatusBadge status="configured" />);
      expect(container.firstChild).toHaveClass("ui-badge--medium");
    });

    it("applies requested size class", () => {
      const { container } = render(<StatusBadge status="configured" size="small" />);
      expect(container.firstChild).toHaveClass("ui-badge--small");
    });

    it("only icon-only badges get the square icon class", () => {
      const { container, rerender } = render(<StatusBadge status="configured" />);
      expect(container.firstChild).toHaveClass("ui-badge--icon");
      rerender(<StatusBadge status="configured" showLabel />);
      expect(container.firstChild).not.toHaveClass("ui-badge--icon");
    });
  });

  describe("Visual Semantics", () => {
    it.each(ALL_STATUSES)("'%s' draws its own icon shape (not colour alone)", (status) => {
      const { container } = render(<StatusBadge status={status} />);
      expect(container.querySelector("svg")).not.toBeNull();
    });
  });
});
