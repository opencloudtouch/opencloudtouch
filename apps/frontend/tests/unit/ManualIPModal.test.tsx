/**
 * Tests for ManualIPModal — Escape key dismissal and a11y attributes.
 *
 * Covers: overlay onKeyDown handler, role attributes, keyboard dismissal.
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
