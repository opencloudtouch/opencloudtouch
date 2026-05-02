/**
 * Tests for ManualIPModal — Escape key dismissal and a11y attributes.
 *
 * Covers: overlay onKeyDown handler, role attributes, keyboard dismissal.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ManualIPModal from "../../src/components/ManualIPModal";

// Mock the settings hooks
vi.mock("../../src/hooks/useSettings", () => ({
  useManualIPs: () => ({ data: ["192.168.1.100"] }),
  useSetManualIPs: () => vi.fn().mockResolvedValue(undefined),
}));

describe("ManualIPModal", () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <ManualIPModal isOpen={false} onClose={mockOnClose} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders modal content when open", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByText("Manual IP Configuration")).toBeInTheDocument();
  });

  it("calls onClose when overlay is clicked", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const overlay = document.querySelector(".modal-overlay")!;
    fireEvent.click(overlay);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("does not close when modal content is clicked", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const content = document.querySelector(".modal-content")!;
    fireEvent.click(content);
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("calls onClose when Escape key is pressed on overlay", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const overlay = document.querySelector(".modal-overlay")!;
    fireEvent.keyDown(overlay, { key: "Escape" });
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("does not close on non-Escape key on overlay", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const overlay = document.querySelector(".modal-overlay")!;
    fireEvent.keyDown(overlay, { key: "Enter" });
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("overlay has role=none for a11y", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const overlay = document.querySelector(".modal-overlay")!;
    expect(overlay).toHaveAttribute("role", "none");
  });

  it("modal content uses native dialog element", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const dialog = document.querySelector("dialog.modal-content")!;
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("open");
  });

  it("pre-fills with existing IPs on open", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveValue("192.168.1.100");
  });
});
