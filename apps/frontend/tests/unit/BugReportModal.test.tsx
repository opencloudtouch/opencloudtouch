/**
 * Tests for BugReportModal component
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";

const mockSubmitBugReport = vi.fn();
const mockShowToast = vi.fn();

// Mock dependencies
vi.mock("../../src/api/bugReport", () => ({
  submitBugReport: mockSubmitBugReport,
}));

vi.mock("../../src/utils/logBuffer", () => ({
  getLogEntries: vi.fn().mockReturnValue([{ level: "info", message: "test" }]),
}));

vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: mockShowToast }),
}));

vi.mock("html2canvas", () => ({
  default: vi.fn().mockResolvedValue({
    toDataURL: vi.fn().mockReturnValue("data:image/jpeg;base64,abc"),
  }),
}));

// react-router-dom mock for useLocation
vi.mock("react-router-dom", () => ({
  useLocation: () => ({ pathname: "/test" }),
}));

async function getBugReportModal() {
  const { default: BugReportModal } = await import("../../src/components/BugReportModal");
  return BugReportModal;
}

describe("BugReportModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSubmitBugReport.mockResolvedValue({ issue_url: "https://github.com/test/issues/1" });
  });

  it("returns null when closed", async () => {
    const BugReportModal = await getBugReportModal();
    const { container } = render(<BugReportModal open={false} onClose={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the dialog when open", async () => {
    const BugReportModal = await getBugReportModal();
    render(<BugReportModal open onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("renders all required form fields", async () => {
    const BugReportModal = await getBugReportModal();
    render(<BugReportModal open onClose={vi.fn()} />);
    expect(screen.getByText(/Bug Description/i)).toBeInTheDocument();
    expect(screen.getByText(/Steps to Reproduce/i)).toBeInTheDocument();
    expect(screen.getByText(/Expected Behavior/i)).toBeInTheDocument();
    expect(screen.getByText(/Installation Type/i)).toBeInTheDocument();
  });

  it("submit button is disabled when form is empty", async () => {
    const BugReportModal = await getBugReportModal();
    render(<BugReportModal open onClose={vi.fn()} />);
    const submitButton = screen.getByRole("button", { name: /Submit Bug Report/i });
    expect(submitButton).toBeDisabled();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const BugReportModal = await getBugReportModal();
    const onClose = vi.fn();
    render(<BugReportModal open onClose={onClose} />);
    const cancelButton = screen.getByRole("button", { name: /Cancel/i });
    fireEvent.click(cancelButton);
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when close button (✕) is clicked", async () => {
    const BugReportModal = await getBugReportModal();
    const onClose = vi.fn();
    render(<BugReportModal open onClose={onClose} />);
    const closeButton = screen.getByRole("button", { name: /Close/i });
    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalled();
  });

  it("enables submit button when all required fields are filled", async () => {
    const BugReportModal = await getBugReportModal();
    render(<BugReportModal open onClose={vi.fn()} />);

    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "This is a detailed bug description that is long enough" } });
    fireEvent.change(screen.getAllByRole("textbox")[1], { target: { value: "1. Click here\n2. Then there\n3. Error" } });
    fireEvent.change(screen.getAllByRole("textbox")[2], { target: { value: "Should work fine" } });

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "docker" } });
    fireEvent.change(selects[1], { target: { value: "raspberry-pi-4" } });

    const submitButton = screen.getByRole("button", { name: /Submit Bug Report/i });
    expect(submitButton).not.toBeDisabled();
  });

  it("submits form and calls onClose on success", async () => {
    const BugReportModal = await getBugReportModal();
    const onClose = vi.fn();
    render(<BugReportModal open onClose={onClose} />);

    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "This is a detailed bug description that is long enough" } });
    fireEvent.change(screen.getAllByRole("textbox")[1], { target: { value: "1. Click here\n2. Then there\n3. Error" } });
    fireEvent.change(screen.getAllByRole("textbox")[2], { target: { value: "Should work fine" } });

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "docker" } });
    fireEvent.change(selects[1], { target: { value: "raspberry-pi-4" } });

    const submitButton = screen.getByRole("button", { name: /Submit Bug Report/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockSubmitBugReport).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.stringContaining("Bug report created"),
        "success",
        10000
      );
    });
  });

  it("shows error toast on submit failure", async () => {
    mockSubmitBugReport.mockRejectedValue(new Error("Network error"));
    const BugReportModal = await getBugReportModal();
    render(<BugReportModal open onClose={vi.fn()} />);

    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "This is a detailed bug description that is long enough" } });
    fireEvent.change(screen.getAllByRole("textbox")[1], { target: { value: "1. Click here\n2. Then there\n3. Error" } });
    fireEvent.change(screen.getAllByRole("textbox")[2], { target: { value: "Should work fine" } });

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "docker" } });
    fireEvent.change(selects[1], { target: { value: "raspberry-pi-4" } });

    fireEvent.click(screen.getByRole("button", { name: /Submit Bug Report/i }));

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.stringContaining("Failed"),
        "error",
        8000
      );
    });
  });

  it("shows 'other' installation field when 'Other' is selected", async () => {
    const BugReportModal = await getBugReportModal();
    render(<BugReportModal open onClose={vi.fn()} />);

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "other" } });

    expect(screen.getByText(/Which installation/i)).toBeInTheDocument();
  });

  it("shows 'other' hardware field when 'Other' hardware is selected", async () => {
    const BugReportModal = await getBugReportModal();
    render(<BugReportModal open onClose={vi.fn()} />);

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[1], { target: { value: "other" } });

    expect(screen.getByText(/Which hardware/i)).toBeInTheDocument();
  });

  it("toggles device checkboxes", async () => {
    const BugReportModal = await getBugReportModal();
    render(<BugReportModal open onClose={vi.fn()} />);

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThan(0);
    fireEvent.click(checkboxes[0]);
    expect(checkboxes[0]).toBeChecked();
    fireEvent.click(checkboxes[0]);
    expect(checkboxes[0]).not.toBeChecked();
  });

  it("calls onClose on native cancel event (Escape) in dialog", async () => {
    const BugReportModal = await getBugReportModal();
    const onClose = vi.fn();
    render(<BugReportModal open onClose={onClose} />);
    const dialog = screen.getByRole("dialog");
    fireEvent(dialog, new Event("cancel"));
    expect(onClose).toHaveBeenCalled();
  });
});
