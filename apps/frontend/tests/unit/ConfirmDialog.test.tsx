import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ConfirmDialog from "../../src/components/ConfirmDialog";

describe("ConfirmDialog", () => {
  const defaultProps = {
    open: true,
    message: "Möchten Sie dieses Preset wirklich löschen?",
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  };

  beforeEach(() => {
    defaultProps.onConfirm.mockClear();
    defaultProps.onCancel.mockClear();
  });

  describe("Visibility", () => {
    it("renders nothing when closed", () => {
      const { container } = render(
        <ConfirmDialog {...defaultProps} open={false} />,
      );
      expect(container.firstChild).toBeNull();
    });

    it("renders dialog when open", () => {
      render(<ConfirmDialog {...defaultProps} />);
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    });
  });

  describe("Content", () => {
    it("shows default title and button labels", () => {
      render(<ConfirmDialog {...defaultProps} />);
      expect(screen.getByText("Confirm", { selector: "h2" })).toBeInTheDocument();
      expect(screen.getByTestId("confirm-dialog-confirm")).toHaveTextContent("Confirm");
      expect(screen.getByTestId("confirm-dialog-cancel")).toHaveTextContent("Cancel");
      expect(screen.getByText(defaultProps.message)).toBeInTheDocument();
    });

    it("uses custom title and button labels", () => {
      render(
        <ConfirmDialog
          {...defaultProps}
          title="Löschen"
          confirmLabel="Ja, löschen"
          cancelLabel="Nein"
        />,
      );
      expect(screen.getByText("Löschen")).toBeInTheDocument();
      expect(screen.getByText("Ja, löschen")).toBeInTheDocument();
      expect(screen.getByText("Nein")).toBeInTheDocument();
    });
  });

  describe("User Interactions", () => {
    it("calls onConfirm when confirm button is clicked", () => {
      render(<ConfirmDialog {...defaultProps} />);
      fireEvent.click(screen.getByTestId("confirm-dialog-confirm"));
      expect(defaultProps.onConfirm).toHaveBeenCalledTimes(1);
      expect(defaultProps.onCancel).not.toHaveBeenCalled();
    });

    it("calls onCancel when cancel button is clicked", () => {
      render(<ConfirmDialog {...defaultProps} />);
      fireEvent.click(screen.getByTestId("confirm-dialog-cancel"));
      expect(defaultProps.onCancel).toHaveBeenCalledTimes(1);
      expect(defaultProps.onConfirm).not.toHaveBeenCalled();
    });

    it("calls onCancel when overlay is clicked", () => {
      render(<ConfirmDialog {...defaultProps} />);
      fireEvent.click(screen.getByTestId("confirm-dialog-overlay"));
      expect(defaultProps.onCancel).toHaveBeenCalledTimes(1);
    });

    it("does NOT call onCancel when dialog body is clicked (stopPropagation)", () => {
      render(<ConfirmDialog {...defaultProps} />);
      fireEvent.click(screen.getByRole("alertdialog"));
      expect(defaultProps.onCancel).not.toHaveBeenCalled();
    });

    it("calls onCancel on Escape key", () => {
      render(<ConfirmDialog {...defaultProps} />);
      fireEvent.keyDown(document, { key: "Escape" });
      expect(defaultProps.onCancel).toHaveBeenCalledTimes(1);
    });

    it("calls onCancel when Escape is pressed on overlay element", () => {
      render(<ConfirmDialog {...defaultProps} />);
      const overlay = screen.getByTestId("confirm-dialog-overlay");
      fireEvent.keyDown(overlay, { key: "Escape" });
      // Both inline onKeyDown and document keydown listener fire
      expect(defaultProps.onCancel).toHaveBeenCalled();
    });

    it("does not call onCancel on non-Escape key on overlay", () => {
      render(<ConfirmDialog {...defaultProps} />);
      const overlay = screen.getByTestId("confirm-dialog-overlay");
      fireEvent.keyDown(overlay, { key: "Enter" });
      expect(defaultProps.onCancel).not.toHaveBeenCalled();
    });
  });

  describe("Accessibility", () => {
    it("has correct ARIA attributes", () => {
      render(<ConfirmDialog {...defaultProps} />);
      const dialog = screen.getByRole("alertdialog");
      expect(dialog).toHaveAttribute("aria-modal", "true");
      expect(dialog).toHaveAttribute("aria-labelledby", "confirm-dialog-title");
      expect(dialog).toHaveAttribute(
        "aria-describedby",
        "confirm-dialog-message",
      );
    });

    it("focuses cancel button on open (safe default)", () => {
      render(<ConfirmDialog {...defaultProps} />);
      expect(screen.getByTestId("confirm-dialog-cancel")).toHaveFocus();
    });
  });
});
