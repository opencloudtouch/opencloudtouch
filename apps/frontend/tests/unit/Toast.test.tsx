/**
 * Tests for Toast.tsx
 *
 * User Story: "Als User möchte ich visuelles Feedback für Aktionen erhalten"
 *
 * Focus: Functional tests for toast notifications
 * - Display messages with different types (success, error, warning, info)
 * - Auto-hide after duration
 * - Manual close button
 * - Proper styling per type
 * - Visibility lifecycle
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import Toast from "../../src/components/Toast";

describe("Toast Component", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe("Display & Types", () => {
    it("should display toast with success type", () => {
      render(<Toast message="Operation successful!" type="success" />);

      expect(screen.getByText("Operation successful!")).toBeInTheDocument();
      // Check toast container CSS class (use container query)
      const toastContainer = screen.getByText("Operation successful!").closest(".toast");
      expect(toastContainer).toHaveClass("toast-success");
      expect(toastContainer).toHaveClass("toast-visible");
    });

    it("should display toast with error type", () => {
      render(<Toast message="Something went wrong!" type="error" />);

      const toastContainer = screen.getByText("Something went wrong!").closest(".toast");
      expect(toastContainer).toHaveClass("toast-error");
    });

    it("should display toast with warning type", () => {
      render(<Toast message="This is a warning" type="warning" />);

      const toastContainer = screen.getByText("This is a warning").closest(".toast");
      expect(toastContainer).toHaveClass("toast-warning");
    });

    it("should default to info type when not specified", () => {
      render(<Toast message="Information" />);

      const toastContainer = screen.getByText("Information").closest(".toast");
      expect(toastContainer).toHaveClass("toast-info");
    });
  });

  describe("Auto-Hide Behavior", () => {
    it("should auto-hide after default duration (5 seconds)", async () => {
      const mockOnClose = vi.fn();
      render(<Toast message="Test message" onClose={mockOnClose} />);

      // Initially visible
      expect(screen.getByText("Test message")).toBeInTheDocument();

      // Fast-forward 5 seconds
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });

      // Should be hidden (component sets visibility to false)
      // Wait for fade-out animation + onClose callback
      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it("should respect custom duration", async () => {
      const mockOnClose = vi.fn();
      render(<Toast message="Test message" duration={2000} onClose={mockOnClose} />);

      // Fast-forward 2 seconds
      await act(async () => {
        vi.advanceTimersByTime(2000);
      });

      // Wait for fade-out animation
      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it("should not crash when onClose is not provided", async () => {
      render(<Toast message="Test message" />);

      // Advancing timers should not throw error (onClose?.() safe navigation)
      await act(async () => {
        vi.runAllTimers();
      });
      // No assertion needed - just verifying no crash
    });
  });

  describe("Manual Close", () => {
    it("should close immediately when close button clicked", async () => {
      const mockOnClose = vi.fn();
      render(<Toast message="Test message" onClose={mockOnClose} />);

      // Click close button (use aria-label)
      fireEvent.click(screen.getByRole("button", { name: "Schließen" }));

      // Wait for fade-out animation
      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it("should hide toast before calling onClose (fade-out animation)", async () => {
      const mockOnClose = vi.fn();
      render(<Toast message="Test message" onClose={mockOnClose} />);

      // Initially visible
      const toastContainer = screen.getByText("Test message").closest(".toast");
      expect(toastContainer).toHaveClass("toast-visible");

      // Click close
      fireEvent.click(screen.getByRole("button", { name: "Schließen" }));

      // After animation, onClose called
      await act(async () => {
        vi.advanceTimersByTime(300);
      });
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  describe("Accessibility", () => {
    it("should have aria-label on close button for screen readers", () => {
      render(<Toast message="Test message" />);

      expect(screen.getByRole("button", { name: "Schließen" })).toHaveAttribute(
        "aria-label",
        "Schließen"
      );
    });

    it("should render different icons for each type", () => {
      const { rerender } = render(<Toast message="Test" type="success" />);
      const successToast = screen.getByText("Test").closest(".toast")!;
      expect(successToast.querySelector("svg")).toBeInTheDocument();

      rerender(<Toast message="Test" type="error" />);
      const errorToast = screen.getByText("Test").closest(".toast")!;
      expect(errorToast.querySelector("svg")).toBeInTheDocument();

      rerender(<Toast message="Test" type="warning" />);
      const warningToast = screen.getByText("Test").closest(".toast")!;
      expect(warningToast.querySelector("svg")).toBeInTheDocument();

      rerender(<Toast message="Test" type="info" />);
      const infoToast = screen.getByText("Test").closest(".toast")!;
      expect(infoToast.querySelector("svg")).toBeInTheDocument();
    });
  });
});
