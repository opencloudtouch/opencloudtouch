/**
 * Tests for Step5ConfigModification — URL normalization logic
 *
 * Covers: normalizeUrl() function, preview display, success message display,
 * regression tests for old_url and new_url values.
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

describe("Step5ConfigModification — URL Normalization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  describe("normalizeUrl() function behavior", () => {
    it("adds default protocol (http) and port (7777) to bare hostname", async () => {
      await renderStep5("hera");

      // Preview should show normalized URL
      await waitFor(() => {
        const preview = document.body.textContent;
        expect(preview).toContain("http://hera:7777");
      });
    });

    it("adds default port (7777) to hostname with protocol", async () => {
      await renderStep5("http://hera");

      await waitFor(() => {
        const preview = document.body.textContent;
        expect(preview).toContain("http://hera:7777");
      });
    });

    it("preserves custom port when specified", async () => {
      await renderStep5("http://hera:8080");

      await waitFor(() => {
        const preview = document.body.textContent;
        expect(preview).toContain("http://hera:8080");
      });
    });

    it("adds protocol and port to bare IP address", async () => {
      await renderStep5("192.168.1.50");

      await waitFor(() => {
        const preview = document.body.textContent;
        expect(preview).toContain("http://192.168.1.50:7777");
      });
    });

    it("preserves https protocol when specified", async () => {
      await renderStep5("https://hera");

      await waitFor(() => {
        const preview = document.body.textContent;
        expect(preview).toContain("https://hera:7777");
      });
    });

    it("handles FQDN with subdomain correctly", async () => {
      await renderStep5("oct.example.com");

      await waitFor(() => {
        const preview = document.body.textContent;
        expect(preview).toContain("http://oct.example.com:7777");
      });
    });

    it("handles localhost correctly", async () => {
      await renderStep5("localhost");

      await waitFor(() => {
        const preview = document.body.textContent;
        expect(preview).toContain("http://localhost:7777");
      });
    });

    it("shows placeholder for empty string", async () => {
      await renderStep5("");

      await waitFor(() => {
        const preview = document.body.textContent;
        // Empty URL should show placeholder "http://..."
        expect(preview).toContain("http://...");
      });
    });
  });

  describe("Preview display (before Apply)", () => {
    it("shows normalized URL in config preview", async () => {
      await renderStep5("hera");

      // Look for preview section showing "Zu: http://hera:7777"
      await waitFor(() => {
        const preview = document.body.textContent;
        expect(preview).toContain("http://hera:7777");
      });
    });

    it("updates preview when server_url changes", async () => {
      await renderStep5("server1");

      await waitFor(() => {
        expect(document.body.textContent).toContain("http://server1:7777");
      });

      // Simulate URL change (e.g., user action triggering new server info)
      cleanup();
      await renderStep5("server2:8080");

      await waitFor(() => {
        expect(document.body.textContent).toContain("http://server2:8080");
      });
    });
  });

  describe("Success message display (after Apply)", () => {
    it("shows normalized URL in success message new_url field", async () => {
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
        new_url: "hera", // Backend returns bare hostname
        backup_path: "/mnt/nv/SoundTouchSdkPrivateCfg.xml.oct-backup",
        diff: "- old\n+ new",
        message: "Config modified",
      });

      await renderStep5("hera");

      await act(async () => {
        getApplyButton().click();
      });

      // Wait for success message
      await waitFor(() => {
        expect(mockModifyConfig).toHaveBeenCalled();
      });

      // Success message should show normalized URL, not bare hostname
      await waitFor(() => {
        const successMsg = document.body.textContent;
        expect(successMsg).toContain("http://hera:7777");
        expect(successMsg).not.toContain('new_url":"hera"'); // Raw JSON should not leak
      });
    });

    it("shows normalized URL even when backend returns IP", async () => {
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
        new_url: "192.168.1.50",
        backup_path: "/mnt/nv/cfg.bak",
        diff: "...",
        message: "OK",
      });

      await renderStep5("192.168.1.50");

      await act(async () => {
        getApplyButton().click();
      });

      await waitFor(() => {
        expect(mockModifyConfig).toHaveBeenCalled();
      });

      // Should show http://192.168.1.50:7777
      await waitFor(() => {
        const successMsg = document.body.textContent;
        expect(successMsg).toContain("http://192.168.1.50:7777");
      });
    });

    it("preserves custom port in success message", async () => {
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
        new_url: "hera",
        backup_path: "/backup",
        diff: "...",
        message: "OK",
      });

      await renderStep5("hera:8080");

      await act(async () => {
        getApplyButton().click();
      });

      await waitFor(() => {
        expect(mockModifyConfig).toHaveBeenCalled();
      });

      // Should show http://hera:8080, not :7777
      await waitFor(() => {
        const successMsg = document.body.textContent;
        expect(successMsg).toContain("http://hera:8080");
      });
    });
  });

  describe("Regression tests — old_url field", () => {
    it("shows representative old_url covering all 4 modified URLs", async () => {
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
        old_url: "https://*.bose.com (4 URLs)", // New format
        new_url: "hera",
        backup_path: "/backup",
        diff: "...",
        message: "OK",
      });

      await renderStep5("hera");

      await act(async () => {
        getApplyButton().click();
      });

      await waitFor(() => {
        expect(mockModifyConfig).toHaveBeenCalled();
      });

      // Should display new old_url format
      await waitFor(() => {
        const successMsg = document.body.textContent;
        expect(successMsg).toContain("https://*.bose.com (4 URLs)");
      });
    });

    it("does NOT show legacy old_url value (bmx.bose.com)", async () => {
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
        new_url: "hera",
        backup_path: "/backup",
        diff: "...",
        message: "OK",
      });

      await renderStep5("hera");

      await act(async () => {
        getApplyButton().click();
      });

      await waitFor(() => {
        expect(mockModifyConfig).toHaveBeenCalled();
      });

      // Legacy value must NOT appear
      await waitFor(() => {
        const successMsg = document.body.textContent;
        expect(successMsg).not.toContain("bmx.bose.com");
      });
    });
  });

  describe("Edge cases", () => {
    it("handles URL with trailing slash", async () => {
      await renderStep5("http://hera:7777/");

      await waitFor(() => {
        // Should strip trailing slash or handle gracefully
        const preview = document.body.textContent;
        // normalizeUrl uses regex that matches until port, so trailing / is ignored
        expect(preview).toContain("http://hera:7777");
      });
    });

    it("handles URL with path (should ignore path)", async () => {
      await renderStep5("http://hera:7777/some/path");

      await waitFor(() => {
        const preview = document.body.textContent;
        // normalizeUrl regex stops at port, path is stripped
        expect(preview).toContain("http://hera:7777");
      });
    });

    it("handles malformed URL gracefully", async () => {
      await renderStep5("ht!tp://invalid");

      await waitFor(() => {
        const preview = document.body.textContent;
        // If regex fails, normalizeUrl returns input unchanged
        expect(preview).toContain("ht!tp://invalid");
      });
    });

    it("handles IPv6 address (edge case)", async () => {
      await renderStep5("[::1]");

      await waitFor(() => {
        const preview = document.body.textContent;
        // IPv6 not explicitly supported by current regex, returns input
        expect(preview).toContain("[::1]");
      });
    });
  });
});
