/**
 * Tests for RestoreExecution component — step-by-step restore progress
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

const mockRestore = vi.fn();
let mockRestoreData: unknown = null;
let mockIsPending = false;
let mockError: Error | null = null;

vi.mock("../../src/hooks/useRestore", () => ({
  useExecuteRestore: () => ({
    mutate: mockRestore,
    data: mockRestoreData,
    isPending: mockIsPending,
    error: mockError,
  }),
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

describe("RestoreExecution", () => {
  const defaultProps = {
    stepNumber: 3,
    deviceIp: "192.168.1.100",
    deviceId: "ABC123",
    restoreType: "clean" as const,
    backupSet: null,
    onComplete: vi.fn(),
    onPrevious: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockRestoreData = null;
    mockIsPending = false;
    mockError = null;
  });

  it("triggers restore on mount", async () => {
    const { default: RestoreExecution } = await import(
      "../../src/components/wizard/RestoreExecution"
    );
    render(<RestoreExecution {...defaultProps} />);
    expect(mockRestore).toHaveBeenCalledWith(
      expect.objectContaining({
        device_ip: "192.168.1.100",
        device_id: "ABC123",
        restore_type: "clean",
        backup_set: null,
        skip_snapshot: false,
      }),
    );
  });

  it("shows loading state during restore", async () => {
    mockIsPending = true;
    const { default: RestoreExecution } = await import(
      "../../src/components/wizard/RestoreExecution"
    );
    render(<RestoreExecution {...defaultProps} />);
    expect(screen.getByText("Restore in progress...")).toBeInTheDocument();
  });

  it("shows error when restore fails", async () => {
    mockError = new Error("SSH timeout");
    const { default: RestoreExecution } = await import(
      "../../src/components/wizard/RestoreExecution"
    );
    render(<RestoreExecution {...defaultProps} />);
    expect(screen.getByText(/SSH timeout/)).toBeInTheDocument();
  });

  it("shows step results when restore completes", async () => {
    mockRestoreData = {
      success: true,
      total_duration_seconds: 12.5,
      steps: [
        { name: "config", status: "completed", message: "Config restored", error: null, duration_seconds: 3.2 },
        { name: "presets", status: "completed", message: "Presets cleared", error: null, duration_seconds: 1.1 },
        { name: "hosts", status: "completed", message: "/etc/hosts cleaned", error: null, duration_seconds: 0.8 },
      ],
    };
    const { default: RestoreExecution } = await import(
      "../../src/components/wizard/RestoreExecution"
    );
    render(<RestoreExecution {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText("Config restored")).toBeInTheDocument();
      expect(screen.getByText("Presets cleared")).toBeInTheDocument();
      expect(screen.getByText("/etc/hosts cleaned")).toBeInTheDocument();
    });
  });

  it("shows success message with total time", async () => {
    mockRestoreData = {
      success: true,
      total_duration_seconds: 8.3,
      steps: [
        { name: "config", status: "completed", message: "Done", error: null, duration_seconds: 8.3 },
      ],
    };
    const { default: RestoreExecution } = await import(
      "../../src/components/wizard/RestoreExecution"
    );
    const { container } = render(<RestoreExecution {...defaultProps} />);
    expect(container.textContent).toContain("8.3s");
  });

  it("shows failed step with error detail", async () => {
    mockRestoreData = {
      success: false,
      total_duration_seconds: 5.0,
      steps: [
        { name: "hosts", status: "failed", message: "Failed to clean hosts", error: "Permission denied", duration_seconds: 0.5 },
      ],
    };
    const { default: RestoreExecution } = await import(
      "../../src/components/wizard/RestoreExecution"
    );
    render(<RestoreExecution {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText("Permission denied")).toBeInTheDocument();
    });
  });
});
