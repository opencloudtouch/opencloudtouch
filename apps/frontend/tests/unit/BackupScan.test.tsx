/**
 * Tests for BackupScan component — scan results display
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

// Mock the restore API hook
const mockScan = vi.fn();
vi.mock("../../src/hooks/useRestore", () => ({
  useScanBackups: () => ({
    mutate: mockScan,
    data: mockScanData,
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

let mockScanData: unknown = null;
let mockIsPending = false;
let mockError: Error | null = null;

describe("BackupScan", () => {
  const defaultProps = {
    stepNumber: 2,
    deviceIp: "192.168.1.100",
    deviceId: "ABC123",
    onBackupSelected: vi.fn(),
    onPrevious: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockScanData = null;
    mockIsPending = false;
    mockError = null;
  });

  it("triggers scan on mount", async () => {
    const { default: BackupScan } = await import("../../src/components/wizard/BackupScan");
    render(<BackupScan {...defaultProps} />);
    expect(mockScan).toHaveBeenCalledWith({
      device_ip: "192.168.1.100",
      device_id: "ABC123",
    });
  });

  it("shows loading state when scanning", async () => {
    mockIsPending = true;
    const { default: BackupScan } = await import("../../src/components/wizard/BackupScan");
    render(<BackupScan {...defaultProps} />);
    expect(screen.getByText("Scanning USB stick...")).toBeInTheDocument();
  });

  it("shows error when scan fails", async () => {
    mockError = new Error("Connection refused");
    const { default: BackupScan } = await import("../../src/components/wizard/BackupScan");
    render(<BackupScan {...defaultProps} />);
    expect(screen.getByText(/Connection refused/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows no-USB warning when USB not mounted", async () => {
    mockScanData = { usb_mounted: false, selected_set: null, error: null };
    const { default: BackupScan } = await import("../../src/components/wizard/BackupScan");
    render(<BackupScan {...defaultProps} />);
    expect(screen.getByText(/No USB stick detected/)).toBeInTheDocument();
  });

  it("shows backup set when found", async () => {
    mockScanData = {
      usb_mounted: true,
      error: null,
      selected_set: {
        device_id: "ABC123",
        backup_date: "2026-01-15",
        is_legacy: false,
        files: [
          {
            filename: "oct-rootfs-ABC123-20260115.tar.gz",
            file_path: "/mnt/USB/oct-backup/oct-rootfs-ABC123-20260115.tar.gz",
            volume_type: "rootfs",
            validation_status: "valid",
            validation_message: null,
          },
        ],
      },
    };
    const { default: BackupScan } = await import("../../src/components/wizard/BackupScan");
    const { container } = render(<BackupScan {...defaultProps} />);
    expect(container.textContent).toContain("Backup found");
    expect(container.textContent).toContain("rootfs");
  });

  it("shows mismatch warning for files with validation warnings", async () => {
    mockScanData = {
      usb_mounted: true,
      error: null,
      selected_set: {
        device_id: "ABC123",
        backup_date: "2026-01-15",
        is_legacy: false,
        files: [
          {
            filename: "oct-rootfs-OTHER-20260115.tar.gz",
            file_path: "/mnt/USB/oct-backup/oct-rootfs-OTHER-20260115.tar.gz",
            volume_type: "rootfs",
            validation_status: "warning",
            validation_message: "Device ID mismatch",
          },
        ],
      },
    };
    const { default: BackupScan } = await import("../../src/components/wizard/BackupScan");
    const { container } = render(<BackupScan {...defaultProps} />);
    expect(container.textContent).toContain("Device ID mismatch");
  });
});
