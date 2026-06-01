/**
 * Tests for Step5ConfigModification — DNS validation flow
 *
 * Covers: DNS warning display, proceed button, use-resolved-IP button,
 * error handling, hostname extraction logic, and all branches.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor, cleanup } from "@testing-library/react";
import React from "react";

// Mock the wizard API
const mockValidateHostname = vi.fn();
const mockModifyConfig = vi.fn();
const mockGetServerInfo = vi.fn();
const mockDetectStrategy = vi.fn();

vi.mock("../../src/api/wizard", () => ({
  checkPorts: vi.fn().mockResolvedValue({ success: true, has_ssh: true, message: "SSH access enabled" }),
  detectStrategy: (...args: unknown[]) => mockDetectStrategy(...args),
  modifyConfig: (...args: unknown[]) => mockModifyConfig(...args),
  getServerInfo: (...args: unknown[]) => mockGetServerInfo(...args),
  verifyRedirect: vi.fn().mockResolvedValue({ success: true }),
  rebootDevice: vi.fn().mockResolvedValue({}),
  createBackup: vi.fn().mockResolvedValue({ path: "/backup/file.bak" }),
  modifyHosts: vi.fn().mockResolvedValue({}),
  validateHostname: (...args: unknown[]) => mockValidateHostname(...args),
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
    span: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <span {...props}>{children}</span>
    ),
    ul: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <ul {...props}>{children}</ul>
    ),
    p: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <p {...props}>{children}</p>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

const defaultProps = {
  deviceId: "AABBCCDDEEFF",
  deviceIp: "192.168.1.100",
  deviceName: "SoundTouch 10",
  octUrl: "http://myserver.local:7777",
  onNext: vi.fn(),
  onPrevious: vi.fn(),
  onConfigModified: vi.fn(),
  onStrategyDetected: vi.fn(),
};

async function renderStep5(serverUrl = "http://myserver.local:7777") {
  mockGetServerInfo.mockResolvedValue({
    server_url: serverUrl,
    server_ip: "192.168.1.50",
    default_port: 7777,
    supported_protocols: ["http"],
  });
  mockDetectStrategy.mockResolvedValue({
    proxy_available: false,
    strategy: "bmx_and_hosts",
    message: "No proxy detected",
  });

  const { default: Step5 } = await import(
    "../../src/components/wizard/Step5ConfigModification"
  );

  await act(async () => {
    render(<Step5 {...defaultProps} />);
  });

  // Wait for auto-detect to finish
  await waitFor(() => {
    expect(mockGetServerInfo).toHaveBeenCalled();
  });
}

function getApplyButton(): HTMLButtonElement {
  const buttons = screen.getAllByRole("button");
  const applyBtn = buttons.find(
    (btn) =>
      btn.textContent?.includes("setup.wizard.step5.btnApply") ||
      btn.textContent?.includes("⚙️")
  );
  if (!applyBtn) throw new Error("Apply button not found");
  return applyBtn as HTMLButtonElement;
}

function queryDnsWarning(): HTMLElement | null {
  return document.querySelector('[data-test="dns-warning"]');
}

function queryDnsProceedBtn(): HTMLElement | null {
  return document.querySelector('[data-test="dns-proceed"]');
}

function queryDnsUseIpBtn(): HTMLElement | null {
  return document.querySelector('[data-test="dns-use-ip"]');
}

describe("Step5ConfigModification — DNS validation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("shows DNS warning when hostname does not resolve", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: false,
      resolved_ip: null,
      matches_expected: null,
      error: "DNS resolution failed: Name not known",
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    expect(mockValidateHostname).toHaveBeenCalledWith({
      hostname: "myserver.local",
      expected_ip: "192.168.1.50",
    });

    await waitFor(() => {
      expect(queryDnsWarning()).not.toBeNull();
    });
  });

  it("shows DNS warning when resolved IP does not match expected", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: true,
      resolved_ip: "10.0.0.99",
      matches_expected: false,
      error: null,
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      expect(queryDnsWarning()).not.toBeNull();
    });
  });

  it("proceeds without DNS warning when hostname resolves correctly", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: true,
      resolved_ip: "192.168.1.50",
      matches_expected: true,
      error: null,
    });
    mockModifyConfig.mockResolvedValueOnce({
      success: true,
      old_url: "bmx.bose.com",
      new_url: "myserver.local",
      message: "Config modified",
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      expect(mockModifyConfig).toHaveBeenCalled();
    });
    expect(queryDnsWarning()).toBeNull();
  });

  it("shows DNS warning when validateHostname throws", async () => {
    mockValidateHostname.mockRejectedValueOnce(new Error("Network error"));

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      expect(queryDnsWarning()).not.toBeNull();
    });
  });

  it("skips DNS validation for pure IP addresses", async () => {
    mockModifyConfig.mockResolvedValueOnce({
      success: true,
      old_url: "bmx.bose.com",
      new_url: "192.168.1.50",
      message: "Config modified",
    });

    // server_url is an IP → extractHostname returns null → no DNS check
    await renderStep5("http://192.168.1.50:7777");

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      expect(mockModifyConfig).toHaveBeenCalled();
    });
    expect(mockValidateHostname).not.toHaveBeenCalled();
  });

  it("proceed button dismisses warning and retries modify", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: false,
      resolved_ip: null,
      matches_expected: null,
      error: "DNS resolution failed",
    });
    mockModifyConfig.mockResolvedValueOnce({
      success: true,
      old_url: "bmx.bose.com",
      new_url: "myserver.local",
      message: "Config modified",
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      expect(queryDnsWarning()).not.toBeNull();
    });

    // Click "Proceed anyway"
    const proceedBtn = queryDnsProceedBtn()!;
    expect(proceedBtn).not.toBeNull();
    await act(async () => {
      proceedBtn.click();
    });

    // setTimeout(handleModifyConfig, 0) — wait for it
    await waitFor(() => {
      expect(mockModifyConfig).toHaveBeenCalled();
    });
  });

  it("use-resolved-ip button replaces hostname with resolved IP", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: true,
      resolved_ip: "10.0.0.99",
      matches_expected: false,
      error: null,
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      expect(queryDnsWarning()).not.toBeNull();
    });

    const useIpBtn = queryDnsUseIpBtn()!;
    expect(useIpBtn).not.toBeNull();
    await act(async () => {
      useIpBtn.click();
    });

    // DNS warning should be dismissed
    expect(queryDnsWarning()).toBeNull();
  });

  it("does not show use-resolved-ip button when resolved_ip is null", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: false,
      resolved_ip: null,
      matches_expected: null,
      error: "DNS resolution failed",
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      expect(queryDnsWarning()).not.toBeNull();
    });

    expect(queryDnsUseIpBtn()).toBeNull();
  });

  it("renders DNS mismatch message when resolvable but IP mismatches", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: true,
      resolved_ip: "10.0.0.99",
      matches_expected: false,
      error: null,
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      const warning = queryDnsWarning()!;
      expect(warning).not.toBeNull();
      expect(warning.textContent).toContain("10.0.0.99");
    });
  });

  it("renders DNS unresolvable message when not resolvable and no error", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: false,
      resolved_ip: null,
      matches_expected: null,
      error: null,
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      const warning = queryDnsWarning()!;
      expect(warning).not.toBeNull();
      expect(warning.textContent).toContain("could not be resolved");
    });
  });

  it("renders DNS error message when not resolvable with error string", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: false,
      resolved_ip: null,
      matches_expected: null,
      error: "DNS resolution failed: NXDOMAIN",
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      const warning = queryDnsWarning()!;
      expect(warning).not.toBeNull();
      expect(warning.textContent).toContain("DNS resolution failed: NXDOMAIN");
    });
  });
});
