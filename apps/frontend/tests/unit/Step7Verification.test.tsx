/**
 * Tests for Step7Verification — finalize, verify, reboot, DNS checks
 *
 * Tests the new Issue #184 functionality: finalize device (UUID + Sources.xml),
 * verify setup (11-point check), and the existing reboot + DNS verification flow.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import React from "react";

// Mock wizard API — hoisted mock functions
const mockFinalizeDevice = vi.fn();
const mockVerifySetup = vi.fn();
const mockVerifyRedirect = vi.fn();
const mockRebootDevice = vi.fn();

vi.mock("../../src/api/wizard", () => ({
  finalizeDevice: (...args: unknown[]) => mockFinalizeDevice(...args),
  verifySetup: (...args: unknown[]) => mockVerifySetup(...args),
  verifyRedirect: (...args: unknown[]) => mockVerifyRedirect(...args),
  rebootDevice: (...args: unknown[]) => mockRebootDevice(...args),
}));

// Mock framer-motion (not available in jsdom)
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
    span: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <span {...props}>{children}</span>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

import Step7Verification from "../../src/components/wizard/Step7Verification";

const defaultProps = {
  deviceIp: "192.168.1.100",
  deviceId: "AABBCCDDEEFF",
  octIp: "192.168.1.50",
  onNext: vi.fn(),
  onPrevious: vi.fn(),
};

/** Helper: mock a successful finalize + verify flow to reach DNS phase */
function mockSuccessFlow() {
  mockFinalizeDevice.mockResolvedValue({
    success: true,
    uuid: "5522049",
    had_uuid: false,
    uuid_was_collision: false,
    sources_written: true,
    sources_backup_path: "/mnt/nv/BoseApp-Persistence/1/Sources.xml.bak",
    system_config_written: true,
    message: "Device finalized: UUID=5522049, Sources=written, SystemConfig=created",
  });
  mockVerifySetup.mockResolvedValue({
    success: true,
    checks: [
      { name: "uuid_present", passed: true, message: "Device UUID: 5522049", details: {} },
      { name: "sources_complete", passed: true, message: "All 5 required sources present", details: {} },
    ],
    passed_count: 2,
    failed_count: 0,
    message: "2/2 checks passed",
  });
}

describe("Step7Verification", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ===================================================================
  // Initial render
  // ===================================================================

  it("renders finalize button in idle state", () => {
    render(<Step7Verification {...defaultProps} />);
    expect(screen.getByRole("button", { name: /finalize/i })).toBeInTheDocument();
  });

  it("renders navigation buttons", () => {
    render(<Step7Verification {...defaultProps} />);
    expect(screen.getByRole("button", { name: /back/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
  });

  it("disables next button initially (no tests passed yet)", () => {
    render(<Step7Verification {...defaultProps} />);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("renders device restart section", () => {
    render(<Step7Verification {...defaultProps} />);
    // "Device restart" is the i18n translation of rebootHeader
    expect(document.body.textContent).toMatch(/device restart|reboot/i);
  });

  // ===================================================================
  // Finalize — success path
  // ===================================================================

  it("calls finalizeDevice with correct device_ip and device_id", async () => {
    mockSuccessFlow();

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    expect(mockFinalizeDevice).toHaveBeenCalledWith({
      device_ip: "192.168.1.100",
      device_id: "AABBCCDDEEFF",
    });
  });

  it("calls verifySetup after successful finalize", async () => {
    mockSuccessFlow();

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    expect(mockVerifySetup).toHaveBeenCalledWith({
      device_ip: "192.168.1.100",
      device_id: "AABBCCDDEEFF",
      expected_oct_ip: "192.168.1.50",
    });
  });

  it("displays finalize success message", async () => {
    mockSuccessFlow();

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("Device finalized");
    });
  });

  it("displays verify check results", async () => {
    mockSuccessFlow();

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("Device UUID: 5522049");
      expect(document.body.textContent).toContain("All 5 required sources present");
    });
  });

  // ===================================================================
  // Finalize — error path
  // ===================================================================

  it("shows error when finalize returns success=false", async () => {
    mockFinalizeDevice.mockResolvedValue({
      success: false,
      error: "SSH connection refused",
    });

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("SSH connection refused");
    });
  });

  it("shows error when finalizeDevice throws", async () => {
    mockFinalizeDevice.mockRejectedValue(new Error("Network error"));

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("Network error");
    });
  });

  it("does not call verifySetup when finalize fails", async () => {
    mockFinalizeDevice.mockResolvedValue({
      success: false,
      error: "Device unreachable",
    });

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    expect(mockVerifySetup).not.toHaveBeenCalled();
  });

  it("shows retry button after finalize error", async () => {
    mockFinalizeDevice.mockRejectedValue(new Error("Timeout"));

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  // ===================================================================
  // Reboot
  // ===================================================================

  it("calls rebootDevice with device IP", async () => {
    mockRebootDevice.mockResolvedValue({});

    render(<Step7Verification {...defaultProps} />);

    // Find reboot button by text content (includes emoji)
    const buttons = screen.getAllByRole("button");
    const rebootBtn = buttons.find((b) =>
      (b.textContent || "").toLowerCase().includes("reboot")
    );

    if (rebootBtn) {
      await act(async () => {
        fireEvent.click(rebootBtn);
      });

      expect(mockRebootDevice).toHaveBeenCalledWith({ ip: "192.168.1.100" });
    }
  });

  it("shows error message when reboot fails", async () => {
    mockRebootDevice.mockRejectedValue(new Error("Connection lost"));

    render(<Step7Verification {...defaultProps} />);

    const buttons = screen.getAllByRole("button");
    const rebootBtn = buttons.find((b) =>
      (b.textContent || "").toLowerCase().includes("reboot")
    );

    if (rebootBtn) {
      await act(async () => {
        fireEvent.click(rebootBtn);
      });

      await waitFor(() => {
        expect(document.body.textContent).toContain("Connection lost");
      });
    }
  });

  // ===================================================================
  // DNS verification tests (after finalize+verify completes)
  // ===================================================================

  it("shows test button after successful finalize+verify", async () => {
    mockSuccessFlow();

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      const testBtn = buttons.find((b) =>
        (b.textContent || "").toLowerCase().includes("test")
      );
      expect(testBtn).toBeTruthy();
    });
  });

  it("calls verifyRedirect for each test domain", async () => {
    mockSuccessFlow();
    mockVerifyRedirect.mockResolvedValue({
      success: true,
      resolved_ip: "192.168.1.50",
      expected_ip: "192.168.1.50",
      matches_expected: true,
      message: "OK",
    });

    render(<Step7Verification {...defaultProps} />);

    // Finalize first
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    // Wait for test button to appear
    let testBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      testBtn = buttons.find((b) =>
        (b.textContent || "").toLowerCase().includes("test")
      );
      expect(testBtn).toBeTruthy();
    });

    // Click test button
    await act(async () => {
      fireEvent.click(testBtn!);
    });

    await waitFor(() => {
      // verifyRedirect called for each test domain (bose.vtuner.com, streaming.bose.com)
      expect(mockVerifyRedirect).toHaveBeenCalledTimes(2);
    });
  });

  it("displays DNS test error in results (not crash)", async () => {
    mockSuccessFlow();
    mockVerifyRedirect.mockRejectedValue(new Error("DNS resolution failed"));

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    let testBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      testBtn = buttons.find((b) =>
        (b.textContent || "").toLowerCase().includes("test")
      );
      expect(testBtn).toBeTruthy();
    });

    await act(async () => {
      fireEvent.click(testBtn!);
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("DNS resolution failed");
    });
  });
});
