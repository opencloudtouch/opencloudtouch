/**
 * Tests for ManualIPModal — dismissal (Escape, backdrop) and a11y attributes of the shared Modal.
 *
 * Covers: native dialog cancel event, overlay click, role/aria attributes.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ManualIPModal from "../../src/components/ManualIPModal";
import { ApiError } from "../../src/api/types";
import { i18next } from "../../src/i18n";

const mockMutateAsync = vi.hoisted(() => vi.fn());

// Mock the settings hooks
vi.mock("../../src/hooks/useSettings", () => ({
  useManualIPs: () => ({ data: ["192.168.1.100"] }),
  useSetManualIPs: () => ({ mutateAsync: mockMutateAsync, isPending: false }),
}));

describe("ManualIPModal", () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
    mockMutateAsync.mockReset();
    mockMutateAsync.mockResolvedValue(undefined);
  });

  it("renders nothing when closed", () => {
    const { container } = render(<ManualIPModal isOpen={false} onClose={mockOnClose} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders modal content when open", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByText("Manual IP Configuration")).toBeInTheDocument();
  });

  it("calls onClose when the dimmed overlay is clicked", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const overlay = document.querySelector('[data-test="modal-overlay"]')!;
    fireEvent.click(overlay);
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

  it("overlay is presentational for a11y", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const overlay = document.querySelector('[data-test="modal-overlay"]')!;
    expect(overlay).toHaveAttribute("role", "presentation");
  });

  it("uses a native modal dialog element labelled by its title", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const dialog = document.querySelector("dialog")!;
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("open");
    expect(dialog).not.toHaveAttribute("role");
    expect(dialog).not.toHaveAttribute("aria-modal");
    expect(dialog).toHaveAttribute("aria-labelledby", "manual-ip-title");
    expect(document.getElementById("manual-ip-title")).toHaveTextContent("Manual IP Configuration");
  });

  it("pre-fills with existing IPs on open", () => {
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveValue("192.168.1.100");
  });

  it("shows the translated message for a coded API error on save", async () => {
    mockMutateAsync.mockRejectedValue(
      new ApiError("Device unreachable: 192.168.1.100", { status: 503, code: "device_unreachable" })
    );
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByRole("button", { name: i18next.t("manualIpModal.save") }));

    expect(await screen.findByText(i18next.t("errors.api.device_unreachable"))).toBeInTheDocument();
    expect(screen.queryByText(/Device unreachable: 192/)).not.toBeInTheDocument();
  });

  it("falls back to the fixed save error for an error without code", async () => {
    mockMutateAsync.mockRejectedValue(new Error("boom"));
    render(<ManualIPModal isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByRole("button", { name: i18next.t("manualIpModal.save") }));

    await waitFor(() =>
      expect(screen.getByText(i18next.t("manualIpModal.saveError"))).toBeInTheDocument()
    );
  });
});
