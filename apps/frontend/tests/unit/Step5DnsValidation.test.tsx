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
      oct_reachable: false,
      error: "DNS resolution failed: Name not known",
      oct_error: null,
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    expect(mockValidateHostname).toHaveBeenCalledWith({
      hostname: "myserver.local",
      port: 7777,
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
      oct_reachable: true,
      error: null,
      oct_error: null,
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
      oct_reachable: true,
      error: null,
      oct_error: null,
    });
    mockModifyConfig.mockResolvedValueOnce({
      success: true,
      old_url: "https://*.bose.com (4 URLs)",
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

  it("validates OCT reachability for IP addresses", async () => {
    // Mock validateHostname to return successful OCT check for IP
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: true, // IPs are always "resolvable" (resolve to themselves)
      resolved_ip: "192.168.1.50",
      matches_expected: null, // No DNS comparison for IPs
      oct_reachable: true,
      error: null,
      oct_error: null,
    });

    mockModifyConfig.mockResolvedValueOnce({
      success: true,
      old_url: "https://*.bose.com (4 URLs)",
      new_url: "192.168.1.50",
      message: "Config modified",
    });

    // server_url is an IP → validateHostname is called to check OCT reachability
    await renderStep5("http://192.168.1.50:7777");

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      expect(mockValidateHostname).toHaveBeenCalledWith({
        hostname: "192.168.1.50",
        port: 7777,
        expected_ip: null, // No DNS comparison for IPs
      });
      expect(mockModifyConfig).toHaveBeenCalled();
    });
    expect(queryDnsWarning()).toBeNull();
  });

  it("proceed button dismisses warning and retries modify with original hostname", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: false,
      resolved_ip: null,
      matches_expected: null,
      oct_reachable: false,
      error: "DNS resolution failed",
      oct_error: null,
    });
    mockModifyConfig.mockResolvedValueOnce({
      success: true,
      old_url: "https://*.bose.com (4 URLs)",
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
      expect(mockModifyConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          target_addr: "http://myserver.local:7777", // Original hostname preserved
        })
      );
    });
  });

  it("does not show use-resolved-ip button (removed from UI)", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: true,
      resolved_ip: "10.0.0.99",
      matches_expected: false,
      oct_reachable: true,
      error: null,
      oct_error: null,
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      expect(queryDnsWarning()).not.toBeNull();
    });

    // "Use resolved IP" button was removed — only "Proceed anyway" remains
    expect(queryDnsUseIpBtn()).toBeNull();
    expect(queryDnsProceedBtn()).not.toBeNull();
  });

  it("renders DNS mismatch message when resolvable but IP mismatches", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: true,
      resolved_ip: "10.0.0.99",
      matches_expected: false,
      oct_reachable: true,
      error: null,
      oct_error: null,
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
      oct_reachable: false,
      error: null,
      oct_error: null,
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
      oct_reachable: false,
      error: "DNS resolution failed: NXDOMAIN",
      oct_error: null,
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

  it("shows DNS warning when hostname resolves but OCT is not reachable", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: true,
      resolved_ip: "192.168.1.50",
      matches_expected: true,
      oct_reachable: false,
      error: null,
      oct_error: "Connection refused at myserver.local:7777",
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      const warning = queryDnsWarning()!;
      expect(warning).not.toBeNull();
      expect(warning.textContent).toContain("Connection refused");
    });
  });

  it("shows DNS warning when OCT returns wrong service", async () => {
    mockValidateHostname.mockResolvedValueOnce({
      resolvable: true,
      resolved_ip: "192.168.1.50",
      matches_expected: true,
      oct_reachable: false,
      error: null,
      oct_error: "Server at myserver.local:7777 is not OpenCloudTouch",
    });

    await renderStep5();

    await act(async () => {
      getApplyButton().click();
    });

    await waitFor(() => {
      const warning = queryDnsWarning()!;
      expect(warning).not.toBeNull();
      expect(warning.textContent).toContain("not OpenCloudTouch");
    });
  });
});
