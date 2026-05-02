/**
 * Smoke tests for BugReportModal component
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

// Mock dependencies
vi.mock("../../src/api/bugReport", () => ({
  submitBugReport: vi.fn().mockResolvedValue({ issue_url: "https://github.com/test/issues/1" }),
}));

vi.mock("../../src/utils/logBuffer", () => ({
  getLogEntries: vi.fn().mockReturnValue([]),
}));

vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: vi.fn() }),
}));

vi.mock("html2canvas", () => ({
  default: vi.fn().mockResolvedValue({ toDataURL: vi.fn().mockReturnValue("data:image/png;base64,abc") }),
}));

describe("BugReportModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns null when closed", async () => {
    const { default: BugReportModal } = await import(
      "../../src/components/BugReportModal"
    );
    const { container } = render(<BugReportModal open={false} onClose={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the dialog when open", async () => {
    const { default: BugReportModal } = await import(
      "../../src/components/BugReportModal"
    );
    render(<BugReportModal open onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("renders all required form fields", async () => {
    const { default: BugReportModal } = await import(
      "../../src/components/BugReportModal"
    );
    render(<BugReportModal open onClose={vi.fn()} />);
    expect(screen.getByText(/Bug Description/i)).toBeInTheDocument();
    expect(screen.getByText(/Steps to Reproduce/i)).toBeInTheDocument();
    expect(screen.getByText(/Expected Behavior/i)).toBeInTheDocument();
    expect(screen.getByText(/Installation Type/i)).toBeInTheDocument();
  });

  it("submit button is disabled when form is empty", async () => {
    const { default: BugReportModal } = await import(
      "../../src/components/BugReportModal"
    );
    render(<BugReportModal open onClose={vi.fn()} />);
    const submitButton = screen.getByRole("button", { name: /Submit Bug Report/i });
    expect(submitButton).toBeDisabled();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const { default: BugReportModal } = await import(
      "../../src/components/BugReportModal"
    );
    const onClose = vi.fn();
    render(<BugReportModal open onClose={onClose} />);
    const cancelButton = screen.getByRole("button", { name: /Cancel/i });
    fireEvent.click(cancelButton);
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when overlay is clicked", async () => {
    const { default: BugReportModal } = await import(
      "../../src/components/BugReportModal"
    );
    const onClose = vi.fn();
    const { container } = render(<BugReportModal open onClose={onClose} />);
    const overlay = container.querySelector(".bug-modal-overlay");
    expect(overlay).not.toBeNull();
    fireEvent.click(overlay!);
    expect(onClose).toHaveBeenCalled();
  });
});
