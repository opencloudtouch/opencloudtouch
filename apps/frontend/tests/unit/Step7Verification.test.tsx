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
      expect(document.body.textContent).toContain("Device UUID set: 5522049");
      expect(document.body.textContent).toContain("Sources.xml written");
      expect(document.body.textContent).toContain("SystemConfigurationDB.xml present");
      const buttons = screen.getAllByRole("button");
      const rebootBtn = buttons.find((b) =>
        (b.textContent || "").toLowerCase().includes("restart")
      );
      expect(rebootBtn).toBeTruthy();
    });
  });

  it("displays finalize checklist items", async () => {
    mockSuccessFlow();

    render(<Step7Verification {...defaultProps} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("Device UUID set: 5522049");
      expect(document.body.textContent).toContain("Sources.xml written");
      expect(document.body.textContent).toContain("SystemConfigurationDB.xml present");
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
      // uuid_present is hidden (duplicate of finalizeUuid), only sources_complete shown
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
      expect(document.body.textContent).toContain("Some checks failed");
    });
  });

  it("shows error when verifySetup itself throws", async () => {
    await reachVerificationPhase();

    mockVerifySetup.mockRejectedValue(new Error("Server unreachable"));

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
      expect(document.body.textContent).toContain("Server unreachable");
    });
  });

  it("falls back to backend message when config_bmx_url has no bmx_url detail", async () => {
    await reachVerificationPhase();

    mockVerifySetup.mockResolvedValue({
      success: true,
      checks: [
        { name: "config_bmx_url", passed: true, message: "BMX URL correct", details: {} },
      ],
      passed_count: 1,
      failed_count: 0,
      message: "1/1 checks passed",
    });
    mockVerifyRedirect.mockResolvedValue({
      success: true,
      resolved_ip: "192.168.1.50",
      expected_ip: "192.168.1.50",
      matches_expected: true,
      message: "OK",
    });

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
      expect(document.body.textContent).toContain("BMX URL correct");
    });
  });

  it("renders ungrouped checks that are not in any defined group", async () => {
    await reachVerificationPhase();

    mockVerifySetup.mockResolvedValue({
      success: true,
      checks: [
        { name: "some_unknown_check", passed: true, message: "Custom check OK", details: {} },
      ],
      passed_count: 1,
      failed_count: 0,
      message: "1/1 checks passed",
    });
    mockVerifyRedirect.mockResolvedValue({
      success: true,
      resolved_ip: "192.168.1.50",
      expected_ip: "192.168.1.50",
      matches_expected: true,
      message: "OK",
    });

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
      expect(document.body.textContent).toContain("Custom check OK");
    });
  });

  it("renders skip button after verification and calls onSkip when clicked", async () => {
    vi.useFakeTimers();
    mockSuccessFlow();
    mockRebootDevice.mockResolvedValue({});
    mockVerifyRedirect.mockResolvedValue({
      success: false,
      resolved_ip: "1.2.3.4",
      expected_ip: "192.168.1.50",
      matches_expected: false,
      message: "Mismatch",
    });

    const onSkip = vi.fn();
    render(<Step7Verification {...defaultProps} onSkip={onSkip} />);

    // Finalize
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /finalize/i }));
    });

    // Reboot
    const rebootBtn = screen.getAllByRole("button").find((b) =>
      (b.textContent || "").toLowerCase().includes("restart")
    );
    await act(async () => {
      fireEvent.click(rebootBtn!);
    });

    // Countdown
    await act(async () => {
      vi.advanceTimersByTime(61000);
    });
    vi.useRealTimers();

    // Full verification
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

    // Wait for skip button to appear
    await waitFor(() => {
      const skipBtn = screen.getAllByRole("button").find((b) =>
        (b.textContent || "").toLowerCase().includes("continue anyway")
      );
      expect(skipBtn).toBeTruthy();
    });

    const skipBtn = screen.getAllByRole("button").find((b) =>
      (b.textContent || "").toLowerCase().includes("continue anyway")
    );
    fireEvent.click(skipBtn!);
    expect(onSkip).toHaveBeenCalledTimes(1);
  });

  // ===================================================================
  // getCheckMessage / formatBmxHostPort branch coverage
  // ===================================================================

  it("formats BMX URL with port as HOST:PORT in check message", async () => {
    await reachVerificationPhase();

    mockVerifySetup.mockResolvedValue({
      success: true,
      checks: [
        { name: "config_bmx_url", passed: true, message: "BMX URL correct", details: { bmx_url: "https://example.com:8443/api" } },
      ],
      passed_count: 1,
      failed_count: 0,
      message: "1/1 checks passed",
    });
    mockVerifyRedirect.mockResolvedValue({ success: true, resolved_ip: "192.168.1.50", expected_ip: "192.168.1.50", matches_expected: true, message: "OK" });

    let verifyBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      verifyBtn = buttons.find((b) => (b.textContent || "").toLowerCase().includes("verification"));
      expect(verifyBtn).toBeTruthy();
    });
    await act(async () => { fireEvent.click(verifyBtn!); });

    await waitFor(() => {
      expect(screen.getByText(/example\.com:8443/)).toBeInTheDocument();
    });
  });

  it("formats BMX URL without port as HOST only", async () => {
    await reachVerificationPhase();

    mockVerifySetup.mockResolvedValue({
      success: true,
      checks: [
        { name: "config_bmx_url", passed: true, message: "BMX URL correct", details: { bmx_url: "https://myserver.local/path" } },
      ],
      passed_count: 1,
      failed_count: 0,
      message: "1/1 checks passed",
    });
    mockVerifyRedirect.mockResolvedValue({ success: true, resolved_ip: "192.168.1.50", expected_ip: "192.168.1.50", matches_expected: true, message: "OK" });

    let verifyBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      verifyBtn = buttons.find((b) => (b.textContent || "").toLowerCase().includes("verification"));
      expect(verifyBtn).toBeTruthy();
    });
    await act(async () => { fireEvent.click(verifyBtn!); });

    await waitFor(() => {
      expect(screen.getByText(/myserver\.local/)).toBeInTheDocument();
    });
  });

  it("falls back to message for invalid BMX URL", async () => {
    await reachVerificationPhase();

    mockVerifySetup.mockResolvedValue({
      success: true,
      checks: [
        { name: "config_bmx_url", passed: true, message: "BMX URL: not-a-url", details: { bmx_url: "not-a-valid-url" } },
      ],
      passed_count: 1,
      failed_count: 0,
      message: "1/1 checks passed",
    });
    mockVerifyRedirect.mockResolvedValue({ success: true, resolved_ip: "192.168.1.50", expected_ip: "192.168.1.50", matches_expected: true, message: "OK" });

    let verifyBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      verifyBtn = buttons.find((b) => (b.textContent || "").toLowerCase().includes("verification"));
      expect(verifyBtn).toBeTruthy();
    });
    await act(async () => { fireEvent.click(verifyBtn!); });

    await waitFor(() => {
      expect(screen.getByText(/BMX URL: not-a-url/)).toBeInTheDocument();
    });
  });

  it("shows translated hosts_ip_correct check with octIp", async () => {
    await reachVerificationPhase();

    mockVerifySetup.mockResolvedValue({
      success: true,
      checks: [
        { name: "hosts_ip_correct", passed: true, message: "Hosts IP correct", details: {} },
      ],
      passed_count: 1,
      failed_count: 0,
      message: "1/1 checks passed",
    });
    mockVerifyRedirect.mockResolvedValue({ success: true, resolved_ip: "192.168.1.50", expected_ip: "192.168.1.50", matches_expected: true, message: "OK" });

    let verifyBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      verifyBtn = buttons.find((b) => (b.textContent || "").toLowerCase().includes("verification"));
      expect(verifyBtn).toBeTruthy();
    });
    await act(async () => { fireEvent.click(verifyBtn!); });

    await waitFor(() => {
      expect(screen.getByText(/192\.168\.1\.50/)).toBeInTheDocument();
    });
  });

  it("translates failed checks with missing details", async () => {
    await reachVerificationPhase();

    mockVerifySetup.mockResolvedValue({
      success: true,
      checks: [
        { name: "sources_complete", passed: false, message: "Missing sources", details: { missing: ["BLUETOOTH", "TUNEIN"] } },
        { name: "hosts_ip_correct", passed: false, message: "IP mismatch", details: {} },
      ],
      passed_count: 0,
      failed_count: 2,
      message: "0/2 checks passed",
    });
    mockVerifyRedirect.mockResolvedValue({ success: true, resolved_ip: "192.168.1.50", expected_ip: "192.168.1.50", matches_expected: true, message: "OK" });

    let verifyBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      verifyBtn = buttons.find((b) => (b.textContent || "").toLowerCase().includes("verification"));
      expect(verifyBtn).toBeTruthy();
    });
    await act(async () => { fireEvent.click(verifyBtn!); });

    await waitFor(() => {
      // Failed sources check with missing details rendered
      expect(screen.getByText(/BLUETOOTH, TUNEIN/)).toBeInTheDocument();
    });
  });

  it("shows failed config_bmx_url with original message", async () => {
    await reachVerificationPhase();

    mockVerifySetup.mockResolvedValue({
      success: true,
      checks: [
        { name: "config_bmx_url", passed: false, message: "BMX URL missing", details: {} },
      ],
      passed_count: 0,
      failed_count: 1,
      message: "0/1 checks passed",
    });
    mockVerifyRedirect.mockResolvedValue({ success: true, resolved_ip: "192.168.1.50", expected_ip: "192.168.1.50", matches_expected: true, message: "OK" });

    let verifyBtn: HTMLElement | undefined;
    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      verifyBtn = buttons.find((b) => (b.textContent || "").toLowerCase().includes("verification"));
      expect(verifyBtn).toBeTruthy();
    });
    await act(async () => { fireEvent.click(verifyBtn!); });

    await waitFor(() => {
      expect(screen.getByText(/BMX URL missing/)).toBeInTheDocument();
    });
  });
});
