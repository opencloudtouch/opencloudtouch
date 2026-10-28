/**
 * Tests for ManualIPModal — dismissal (Escape, backdrop) and a11y attributes of the shared Modal.
 *
 * Covers: native dialog cancel event, overlay click, role/aria attributes.
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

  it("calls onClose when the dimmed overlay is clicked", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const backdrop = document.querySelector(".dlg-backdrop")!;
    fireEvent.click(backdrop);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("does not close when modal content is clicked", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const content = document.querySelector('[data-test="modal-content"]')!;
    fireEvent.click(content);
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("calls onClose when the native dialog is cancelled (Escape)", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const dialog = document.querySelector("dialog")!;
    const cancel = new Event("cancel", { cancelable: true });
    dialog.dispatchEvent(cancel);
    expect(cancel.defaultPrevented).toBe(true); // React state stays the single source of truth
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("does not close on an Enter key press on the overlay", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const overlay = document.querySelector('[data-test="modal-overlay"]')!;
    fireEvent.keyDown(overlay, { key: "Enter" });
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("overlay is a plain wrapper without an ARIA role", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const overlay = document.querySelector('[data-test="modal-overlay"]')!;
    expect(overlay).not.toHaveAttribute("role");
  });

  it("uses a native modal dialog element labelled by its title", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const dialog = document.querySelector("dialog")!;
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("open");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby", "manual-ip-title");
    expect(document.getElementById("manual-ip-title")).toHaveTextContent("Manual IP Configuration");
  });

  it("pre-fills with existing IPs on open", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveValue("192.168.1.100");
  });
});
