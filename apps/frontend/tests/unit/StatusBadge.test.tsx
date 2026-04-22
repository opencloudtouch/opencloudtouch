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

  describe("Rendering", () => {
    it.each(ALL_STATUSES)("renders icon for '%s' status", (status) => {
      const { container } = render(<StatusBadge status={status} />);
      const icon = container.querySelector(".status-icon");
      expect(icon).toBeInTheDocument();
      expect(icon?.textContent).toBeTruthy();
    });

    it("does not show label by default", () => {
      render(<StatusBadge status="configured" />);
      expect(screen.queryByText("Konfiguriert")).not.toBeInTheDocument();
    });

    it("shows label when showLabel is true", () => {
      render(<StatusBadge status="configured" showLabel />);
      expect(screen.getByText("Konfiguriert")).toBeInTheDocument();
    });
  });

  describe("Status Labels", () => {
    const EXPECTED_LABELS: Record<SetupStatus, string> = {
      unconfigured: "Nicht konfiguriert",
      pending: "Setup läuft...",
      configured: "Konfiguriert",
      failed: "Fehlgeschlagen",
      outdated: "Veraltet",
      offline: "Offline",
      unknown: "Unbekannt",
    };

    it.each(Object.entries(EXPECTED_LABELS))(
      "shows correct label for '%s'",
      (status, expectedLabel) => {
        render(
          <StatusBadge status={status as SetupStatus} showLabel />,
        );
        expect(screen.getByText(expectedLabel)).toBeInTheDocument();
      },
    );
  });

  describe("CSS Classes", () => {
    it("applies status-specific class", () => {
      const { container } = render(<StatusBadge status="failed" />);
      expect(container.firstChild).toHaveClass("status-failed");
    });

    it("applies medium size by default", () => {
      const { container } = render(<StatusBadge status="configured" />);
      expect(container.firstChild).toHaveClass("status-medium");
    });

    it("applies requested size class", () => {
      const { container } = render(
        <StatusBadge status="configured" size="small" />,
      );
      expect(container.firstChild).toHaveClass("status-small");
    });
  });

  describe("Visual Semantics", () => {
    it("configured shows success icon ✅", () => {
      const { container } = render(<StatusBadge status="configured" />);
      expect(container.querySelector(".status-icon")?.textContent).toBe("✅");
    });

    it("failed shows error icon ❌", () => {
      const { container } = render(<StatusBadge status="failed" />);
      expect(container.querySelector(".status-icon")?.textContent).toBe("❌");
    });

    it("offline shows signal icon 📡", () => {
      const { container } = render(<StatusBadge status="offline" />);
      expect(container.querySelector(".status-icon")?.textContent).toBe("📡");
    });
  });
});
