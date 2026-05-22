/**
 * Tests for Step7Verification — finalize, reboot, full verification
 *
 * Tests the Issue #184 flow: finalize device (UUID + Sources.xml + SystemConfig),
 * mandatory reboot with countdown, then full verification (verify_setup + DNS).
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
      { name: "uuid_present", passed: true, message: "Device UUID: 5522049", details: { uuid: "5522049" } },
      { name: "sources_complete", passed: true, message: "All 5 required sources present", details: { found: ["AUX","BLUETOOTH","QPLAY","TUNEIN","STORED_MUSIC","PRODUCT"], missing: [] } },
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

  it("does not show reboot section before finalize", () => {
    render(<Step7Verification {...defaultProps} />);
    // Reboot section only appears after finalize succeeds
    const buttons = screen.getAllByRole("button");
    const rebootBtn = buttons.find((b) =>
      (b.textContent || "").toLowerCase().includes("restart device")
    );
    expect(rebootBtn).toBeFalsy();
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

  it("does not call verifySetup immediately after finalize (needs reboot first)", async () => {
    mockSuccessFlow();

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    // verifySetup must NOT be called right after finalize — reboot is required first
    expect(mockVerifySetup).not.toHaveBeenCalled();
  });

  it("shows reboot button after successful finalize", async () => {
    mockSuccessFlow();

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("Device finalized");
      const buttons = screen.getAllByRole("button");
      const rebootBtn = buttons.find((b) =>
        (b.textContent || "").toLowerCase().includes("restart")
      );
      expect(rebootBtn).toBeTruthy();
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

  it("displays verify check results after full verification", async () => {
    vi.useFakeTimers();
    mockSuccessFlow();
    mockRebootDevice.mockResolvedValue({});

    render(<Step7Verification {...defaultProps} />);

    // 1. Finalize
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    // 2. Reboot
    const buttons = screen.getAllByRole("button");
    const rebootBtn = buttons.find((b) =>
      (b.textContent || "").toLowerCase().includes("restart")
    );
    await act(async () => {
      fireEvent.click(rebootBtn!);
    });

    // 3. Fast-forward countdown
    await act(async () => {
      vi.advanceTimersByTime(61000);
    });

    vi.useRealTimers();

    // 4. Click full verification
    await waitFor(() => {
      const btns = screen.getAllByRole("button");
      const verifyBtn = btns.find((b) =>
        (b.textContent || "").toLowerCase().includes("verification")
      );
      expect(verifyBtn).toBeTruthy();
    });

    const btns2 = screen.getAllByRole("button");
    const verifyBtn = btns2.find((b) =>
      (b.textContent || "").toLowerCase().includes("verification")
    );
    await act(async () => {
      fireEvent.click(verifyBtn!);
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("Device UUID: 5522049");
      expect(document.body.textContent).toContain("All required sources present");
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
  // Reboot (after finalize)
  // ===================================================================

  it("calls rebootDevice with device IP after finalize", async () => {
    mockSuccessFlow();
    mockRebootDevice.mockResolvedValue({});

    render(<Step7Verification {...defaultProps} />);

    // Finalize first
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    // Find reboot/restart button
    const buttons = screen.getAllByRole("button");
    const rebootBtn = buttons.find((b) =>
      (b.textContent || "").toLowerCase().includes("restart")
    );
    expect(rebootBtn).toBeTruthy();

    await act(async () => {
      fireEvent.click(rebootBtn!);
    });

    expect(mockRebootDevice).toHaveBeenCalledWith({ ip: "192.168.1.100" });
  });

  it("shows error message when reboot fails", async () => {
    mockSuccessFlow();
    mockRebootDevice.mockRejectedValue(new Error("Connection lost"));

    render(<Step7Verification {...defaultProps} />);

    // Finalize first
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    const buttons = screen.getAllByRole("button");
    const rebootBtn = buttons.find((b) =>
      (b.textContent || "").toLowerCase().includes("restart")
    );

    expect(rebootBtn).toBeTruthy();
    await act(async () => {
      fireEvent.click(rebootBtn!);
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("Connection lost");
    });
  });

  // ===================================================================
  // Full verification (after reboot)
  // ===================================================================

  /** Helper: finalize + reboot + countdown to reach verification phase */
  async function reachVerificationPhase() {
    vi.useFakeTimers();
    mockSuccessFlow();
    mockRebootDevice.mockResolvedValue({});

    render(<Step7Verification {...defaultProps} />);

    // Finalize
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    // Reboot
    const buttons = screen.getAllByRole("button");
    const rebootBtn = buttons.find((b) =>
      (b.textContent || "").toLowerCase().includes("restart")
    );
    await act(async () => {
      fireEvent.click(rebootBtn!);
    });

    // Fast-forward countdown
    await act(async () => {
      vi.advanceTimersByTime(61000);
    });

    // Switch back to real timers so waitFor works
    vi.useRealTimers();
  }

  it("shows full verification button after reboot completes", async () => {
    await reachVerificationPhase();

    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      const verifyBtn = buttons.find((b) =>
        (b.textContent || "").toLowerCase().includes("verification")
      );
      expect(verifyBtn).toBeTruthy();
    });
  });

  it("calls verifySetup and verifyRedirect during full verification", async () => {
    await reachVerificationPhase();

    mockVerifyRedirect.mockResolvedValue({
      success: true,
      resolved_ip: "192.168.1.50",
      expected_ip: "192.168.1.50",
      matches_expected: true,
      message: "OK",
    });

    // Click full verification button
    let verifyBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      verifyBtn = buttons.find((b) =>
        (b.textContent || "").toLowerCase().includes("verification")
      );
      expect(verifyBtn).toBeTruthy();
    });

    await act(async () => {
      fireEvent.click(verifyBtn!);
    });

    await waitFor(() => {
      expect(mockVerifySetup).toHaveBeenCalledWith({
        device_ip: "192.168.1.100",
        device_id: "AABBCCDDEEFF",
        expected_oct_ip: "192.168.1.50",
      });
      // verifyRedirect called for each test domain (bose.vtuner.com, streaming.bose.com)
      expect(mockVerifyRedirect).toHaveBeenCalledTimes(2);
    });
  });

  it("displays DNS test error in results (not crash)", async () => {
    await reachVerificationPhase();

    mockVerifyRedirect.mockRejectedValue(new Error("DNS resolution failed"));

    let verifyBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      verifyBtn = buttons.find((b) =>
        (b.textContent || "").toLowerCase().includes("verification")
      );
      expect(verifyBtn).toBeTruthy();
    });

    await act(async () => {
      fireEvent.click(verifyBtn!);
    });

    await waitFor(() => {
      // DNS errors are caught and shown as failed checks with N/A resolved IP
      expect(document.body.textContent).toContain("N/A");
      expect(document.body.textContent).toContain("Some checks failed");
    });
  });
});
